// TokoOps.exe — Rust shell (std-only) around the TokoOps Offline web app.
// Serves the embedded app on 127.0.0.1 and bridges to the REAL Python
// generators (byte-identical copies of the scripts Muse runs) using an
// embedded CPython for Windows. No external crates.

use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{self, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static APP_HTML: &[u8] = include_bytes!("../../app/tokoops.html");
static PY_BUNDLE_ZIP: &[u8] = include_bytes!("../assets/python-bundle.zip");
static SCRIPT_RESI: &[u8] = include_bytes!("../../generators/resi_merah3.py");
static SCRIPT_FINAL5: &[u8] = include_bytes!("../../generators/laporan_final5.py");
static SCRIPT_BARU: &[u8] = include_bytes!("../../generators/laporan_baru.py");
static SCRIPT_SHANGHAI: &[u8] = include_bytes!("../../generators/laporan_shanghai.py");

const BUNDLE_STAMP: &str = "bundle-v1";
static COUNTER: AtomicU64 = AtomicU64::new(0);

// ---------------------------------------------------------------- data dir

fn data_dir() -> PathBuf {
    if let Ok(d) = env::var("TOKOOPS_DATA") {
        if !d.is_empty() {
            return PathBuf::from(d);
        }
    }
    #[cfg(windows)]
    {
        if let Ok(local) = env::var("LOCALAPPDATA") {
            if !local.is_empty() {
                return PathBuf::from(local).join("TokoOps");
            }
        }
        if let Ok(exe) = env::current_exe() {
            if let Some(dir) = exe.parent() {
                return dir.join("TokoOps-data");
            }
        }
    }
    #[cfg(not(windows))]
    {
        if let Ok(home) = env::var("HOME") {
            if !home.is_empty() {
                return PathBuf::from(home).join(".cache").join("tokoops");
            }
        }
    }
    PathBuf::from("tokoops-data")
}

fn bundle_dir() -> PathBuf {
    data_dir().join(BUNDLE_STAMP)
}

fn scripts_dir() -> PathBuf {
    if let Ok(s) = env::var("TOKOOPS_SCRIPTS") {
        if !s.is_empty() {
            return PathBuf::from(s);
        }
    }
    bundle_dir().join("app-scripts")
}

fn python_cmd() -> String {
    if let Ok(p) = env::var("TOKOOPS_PYTHON") {
        if !p.is_empty() {
            return p;
        }
    }
    #[cfg(windows)]
    {
        return bundle_dir().join("python.exe").to_string_lossy().into_owned();
    }
    #[cfg(not(windows))]
    {
        return "python3".to_string();
    }
}

// ---------------------------------------------------------------- inflate
// Minimal DEFLATE (RFC 1951) decoder: stored, fixed-Huffman and
// dynamic-Huffman blocks. Enough to read the zip bundle.

struct BitReader<'a> {
    data: &'a [u8],
    pos: usize, // byte position
    bit: u32,   // bit position within byte
}

impl<'a> BitReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        BitReader { data, pos: 0, bit: 0 }
    }
    fn bits(&mut self, n: u32) -> io::Result<u32> {
        let mut v: u32 = 0;
        for i in 0..n {
            if self.pos >= self.data.len() {
                return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "deflate eof"));
            }
            let b = (self.data[self.pos] >> self.bit) & 1;
            v |= (b as u32) << i;
            self.bit += 1;
            if self.bit == 8 {
                self.bit = 0;
                self.pos += 1;
            }
        }
        Ok(v)
    }
    fn align_byte(&mut self) {
        if self.bit != 0 {
            self.bit = 0;
            self.pos += 1;
        }
    }
}

struct Huffman {
    // map (len << 16 | code) -> symbol
    map: HashMap<u32, u16>,
    max_len: u32,
}

impl Huffman {
    fn new(lengths: &[u8]) -> Huffman {
        let max_len = *lengths.iter().max().unwrap_or(&0) as u32;
        let mut bl_count = vec![0u32; (max_len + 1) as usize];
        for &l in lengths {
            if l > 0 {
                bl_count[l as usize] += 1;
            }
        }
        let mut next_code = vec![0u32; (max_len + 1) as usize];
        let mut code: u32 = 0;
        for bits in 1..=(max_len as usize) {
            code = (code + bl_count[bits - 1]) << 1;
            next_code[bits] = code;
        }
        let mut map = HashMap::new();
        for (sym, &l) in lengths.iter().enumerate() {
            if l > 0 {
                let l = l as usize;
                let c = next_code[l];
                next_code[l] += 1;
                // Huffman codes are read MSB-first; store reversed-bit key by
                // decoding incrementally instead: key = (len, code as read).
                map.insert(((l as u32) << 16) | c, sym as u16);
            }
        }
        Huffman { map, max_len }
    }
    fn decode(&self, br: &mut BitReader) -> io::Result<u16> {
        let mut code: u32 = 0;
        for len in 1..=self.max_len {
            code = (code << 1) | br.bits(1)?;
            if let Some(&sym) = self.map.get(&(len << 16 | code)) {
                return Ok(sym);
            }
        }
        Err(io::Error::new(io::ErrorKind::InvalidData, "bad huffman code"))
    }
}

const LENGTH_BASE: [u16; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131,
    163, 195, 227, 258,
];
const LENGTH_EXTRA: [u32; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];
const DIST_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
    2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
];
const DIST_EXTRA: [u32; 30] = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13,
    13,
];

fn inflate(data: &[u8]) -> io::Result<Vec<u8>> {
    let mut br = BitReader::new(data);
    let mut out: Vec<u8> = Vec::new();
    loop {
        let bfinal = br.bits(1)?;
        let btype = br.bits(2)?;
        match btype {
            0 => {
                br.align_byte();
                if br.pos + 4 > data.len() {
                    return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "stored hdr"));
                }
                let len = u16::from_le_bytes([data[br.pos], data[br.pos + 1]]) as usize;
                br.pos += 4; // skip LEN + NLEN
                if br.pos + len > data.len() {
                    return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "stored data"));
                }
                out.extend_from_slice(&data[br.pos..br.pos + len]);
                br.pos += len;
            }
            1 => {
                let mut lit_lengths = [0u8; 288];
                for i in 0..144 {
                    lit_lengths[i] = 8;
                }
                for i in 144..256 {
                    lit_lengths[i] = 9;
                }
                for i in 256..280 {
                    lit_lengths[i] = 7;
                }
                for i in 280..288 {
                    lit_lengths[i] = 8;
                }
                let lit = Huffman::new(&lit_lengths);
                let dist_lengths = [5u8; 30];
                let dist = Huffman::new(&dist_lengths);
                inflate_block(&mut br, &lit, &dist, &mut out)?;
            }
            2 => {
                let hlit = br.bits(5)? as usize + 257;
                let hdist = br.bits(5)? as usize + 1;
                let hclen = br.bits(4)? as usize + 4;
                const ORDER: [usize; 19] = [
                    16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15,
                ];
                let mut code_lengths = [0u8; 19];
                for i in 0..hclen {
                    code_lengths[ORDER[i]] = br.bits(3)? as u8;
                }
                let code_huff = Huffman::new(&code_lengths);
                let total = hlit + hdist;
                let mut lengths = vec![0u8; total];
                let mut i = 0;
                while i < total {
                    let sym = code_huff.decode(&mut br)?;
                    match sym {
                        0..=15 => {
                            lengths[i] = sym as u8;
                            i += 1;
                        }
                        16 => {
                            if i == 0 {
                                return Err(io::Error::new(
                                    io::ErrorKind::InvalidData,
                                    "repeat with no prev",
                                ));
                            }
                            let prev = lengths[i - 1];
                            let rep = 3 + br.bits(2)? as usize;
                            for _ in 0..rep {
                                if i >= total {
                                    break;
                                }
                                lengths[i] = prev;
                                i += 1;
                            }
                        }
                        17 => {
                            let rep = 3 + br.bits(3)? as usize;
                            i += rep;
                        }
                        18 => {
                            let rep = 11 + br.bits(7)? as usize;
                            i += rep;
                        }
                        _ => {
                            return Err(io::Error::new(io::ErrorKind::InvalidData, "bad cl sym"));
                        }
                    }
                }
                if i > total {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, "cl overflow"));
                }
                let lit = Huffman::new(&lengths[..hlit]);
                let dist = Huffman::new(&lengths[hlit..]);
                inflate_block(&mut br, &lit, &dist, &mut out)?;
            }
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "bad btype")),
        }
        if bfinal == 1 {
            break;
        }
    }
    Ok(out)
}

fn inflate_block(
    br: &mut BitReader,
    lit: &Huffman,
    dist: &Huffman,
    out: &mut Vec<u8>,
) -> io::Result<()> {
    loop {
        let sym = lit.decode(br)?;
        match sym {
            0..=255 => out.push(sym as u8),
            256 => return Ok(()),
            257..=285 => {
                let idx = (sym - 257) as usize;
                if idx >= 29 {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, "len sym"));
                }
                let len = LENGTH_BASE[idx] as usize + br.bits(LENGTH_EXTRA[idx])? as usize;
                let dsym = dist.decode(br)? as usize;
                if dsym >= 30 {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, "dist sym"));
                }
                let d = DIST_BASE[dsym] as usize + br.bits(DIST_EXTRA[dsym])? as usize;
                if d > out.len() {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, "dist too far"));
                }
                let start = out.len() - d;
                for k in 0..len {
                    let b = out[start + k];
                    out.push(b);
                }
            }
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "bad lit sym")),
        }
    }
}

// ---------------------------------------------------------------- zip read

fn u16le(b: &[u8], o: usize) -> u16 {
    u16::from_le_bytes([b[o], b[o + 1]])
}
fn u32le(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]])
}

fn extract_zip(zip: &[u8], dest: &Path) -> io::Result<usize> {
    // Find End Of Central Directory record.
    let mut eocd: Option<usize> = None;
    if zip.len() >= 22 {
        let start = zip.len().saturating_sub(22 + 65536);
        let mut i = zip.len() - 22;
        loop {
            if u32le(zip, i) == 0x06054b50 {
                eocd = Some(i);
                break;
            }
            if i == start {
                break;
            }
            i -= 1;
        }
    }
    let eocd = eocd.ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "no EOCD"))?;
    let count = u16le(zip, eocd + 10) as usize;
    let mut cd = u32le(zip, eocd + 16) as usize;
    let mut written = 0usize;
    for _ in 0..count {
        if cd + 46 > zip.len() || u32le(zip, cd) != 0x02014b50 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "bad CD entry"));
        }
        let method = u16le(zip, cd + 10);
        let csize = u32le(zip, cd + 20) as usize;
        let name_len = u16le(zip, cd + 28) as usize;
        let extra_len = u16le(zip, cd + 30) as usize;
        let comment_len = u16le(zip, cd + 32) as usize;
        let lho = u32le(zip, cd + 42) as usize;
        let name = String::from_utf8_lossy(&zip[cd + 46..cd + 46 + name_len]).into_owned();
        cd += 46 + name_len + extra_len + comment_len;

        // Sanitize: skip absolute paths and parent traversals.
        let rel = name.replace('\\', "/");
        if rel.starts_with('/') || rel.split('/').any(|p| p == "..") {
            continue;
        }
        let out_path = dest.join(&rel);
        if rel.ends_with('/') {
            fs::create_dir_all(&out_path)?;
            continue;
        }
        // Local header -> data offset.
        if lho + 30 > zip.len() || u32le(zip, lho) != 0x04034b50 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "bad local hdr"));
        }
        let ln = u16le(zip, lho + 26) as usize;
        let le = u16le(zip, lho + 28) as usize;
        let data_off = lho + 30 + ln + le;
        if data_off + csize > zip.len() {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "entry out of range"));
        }
        let raw = &zip[data_off..data_off + csize];
        let bytes = match method {
            0 => raw.to_vec(),
            8 => inflate(raw)?,
            _ => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!("unsupported zip method {method}"),
                ))
            }
        };
        if let Some(parent) = out_path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&out_path, &bytes)?;
        written += 1;
    }
    Ok(written)
}

// ---------------------------------------------------------------- extract

fn ensure_extracted() -> io::Result<()> {
    let bdir = bundle_dir();
    let stamp = bdir.join(".done");
    if stamp.exists() {
        return Ok(());
    }
    fs::create_dir_all(&bdir)?;
    if cfg!(windows) || env::var("TOKOOPS_PYTHON").is_err() {
        // Extract the embedded CPython bundle (needed on Windows; harmless
        // elsewhere but skipped on non-Windows without override to save time).
        if cfg!(windows) {
            let n = extract_zip(PY_BUNDLE_ZIP, &bdir)?;
            eprintln!("[tokoops] extracted python bundle: {n} files");
        }
    }
    let sdir = scripts_dir();
    fs::create_dir_all(&sdir)?;
    fs::write(sdir.join("resi_merah3.py"), SCRIPT_RESI)?;
    fs::write(sdir.join("laporan_final5.py"), SCRIPT_FINAL5)?;
    fs::write(sdir.join("laporan_baru.py"), SCRIPT_BARU)?;
    fs::write(sdir.join("laporan_shanghai.py"), SCRIPT_SHANGHAI)?;
    fs::create_dir_all(data_dir().join("work"))?;
    fs::create_dir_all(data_dir().join("mplconfig"))?;
    fs::write(&stamp, b"ok")?;
    eprintln!("[tokoops] bundle ready at {}", bdir.display());
    Ok(())
}

// ---------------------------------------------------------------- http util

fn percent_decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'%' if i + 2 < bytes.len() => {
                let h = hex_val(bytes[i + 1]);
                let l = hex_val(bytes[i + 2]);
                if let (Some(h), Some(l)) = (h, l) {
                    out.push(h * 16 + l);
                    i += 3;
                } else {
                    out.push(bytes[i]);
                    i += 1;
                }
            }
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn hex_val(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}

fn parse_query(q: &str) -> HashMap<String, String> {
    let mut m = HashMap::new();
    for pair in q.split('&') {
        if pair.is_empty() {
            continue;
        }
        let mut it = pair.splitn(2, '=');
        let k = percent_decode(it.next().unwrap_or(""));
        let v = percent_decode(it.next().unwrap_or(""));
        m.insert(k, v);
    }
    m
}

struct Request {
    method: String,
    path: String,
    query: HashMap<String, String>,
    body: Vec<u8>,
}

fn read_request(stream: &mut TcpStream) -> io::Result<Option<Request>> {
    // Read until CRLFCRLF (headers), cap header size at 64 KB.
    let mut buf: Vec<u8> = Vec::with_capacity(16384);
    let mut chunk = [0u8; 8192];
    let header_end;
    loop {
        if let Some(pos) = find_subslice(&buf, b"\r\n\r\n") {
            header_end = pos + 4;
            break;
        }
        if buf.len() > 65536 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "headers too large"));
        }
        let n = stream.read(&mut chunk)?;
        if n == 0 {
            return Ok(None);
        }
        buf.extend_from_slice(&chunk[..n]);
    }
    let head = String::from_utf8_lossy(&buf[..header_end]).into_owned();
    let mut lines = head.lines();
    let request_line = lines.next().unwrap_or("");
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let target = parts.next().unwrap_or("/").to_string();
    let mut content_length: usize = 0;
    for line in lines {
        let mut kv = line.splitn(2, ':');
        let name = kv.next().unwrap_or("").trim().to_ascii_lowercase();
        if name == "content-length" {
            content_length = kv.next().unwrap_or("0").trim().parse().unwrap_or(0);
        }
    }
    if content_length > 16 * 1024 * 1024 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "body too large"));
    }
    let mut body: Vec<u8> = buf.split_off(header_end);
    while body.len() < content_length {
        let n = stream.read(&mut chunk)?;
        if n == 0 {
            break;
        }
        body.extend_from_slice(&chunk[..n]);
    }
    body.truncate(content_length);
    let (path, query) = match target.find('?') {
        Some(i) => (
            target[..i].to_string(),
            parse_query(&target[i + 1..]),
        ),
        None => (target, HashMap::new()),
    };
    Ok(Some(Request {
        method,
        path,
        query,
        body,
    }))
}

fn find_subslice(hay: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || hay.len() < needle.len() {
        return None;
    }
    hay.windows(needle.len()).position(|w| w == needle)
}

fn respond(
    stream: &mut TcpStream,
    status: &str,
    content_type: &str,
    body: &[u8],
    extra_headers: &str,
) -> io::Result<()> {
    let head = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n{extra_headers}\r\n",
        body.len()
    );
    stream.write_all(head.as_bytes())?;
    stream.write_all(body)?;
    stream.flush()
}

fn respond_text(stream: &mut TcpStream, status: &str, text: &str) -> io::Result<()> {
    respond(stream, status, "text/plain; charset=utf-8", text.as_bytes(), "")
}

// ---------------------------------------------------------------- pages

const OVERLAY: &str = "<a href=\"/python-pdf\" target=\"_blank\" style=\"position:fixed;right:14px;bottom:14px;z-index:99999;background:#b3541e;color:#fff;padding:10px 16px;border-radius:999px;font:600 14px system-ui,sans-serif;text-decoration:none;box-shadow:0 4px 14px rgba(0,0,0,.35)\">PDF Python Asli</a>";

fn serve_app(stream: &mut TcpStream) -> io::Result<()> {
    let html = String::from_utf8_lossy(APP_HTML).into_owned();
    let lower = html.to_ascii_lowercase();
    let page = if let Some(pos) = lower.rfind("</body>") {
        let mut s = String::with_capacity(html.len() + OVERLAY.len());
        s.push_str(&html[..pos]);
        s.push_str(OVERLAY);
        s.push_str(&html[pos..]);
        s
    } else {
        format!("{html}{OVERLAY}")
    };
    respond(stream, "200 OK", "text/html; charset=utf-8", page.as_bytes(), "")
}

const BRIDGE_PAGE: &str = r##"<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TokoOps — PDF Python Asli</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f6f1ea; color: #26221d; }
  .wrap { max-width: 640px; margin: 24px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 14px; padding: 20px 22px; box-shadow: 0 2px 10px rgba(0,0,0,.08); }
  h1 { font-size: 20px; margin: 0 0 4px; }
  p.sub { margin: 0 0 16px; color: #6b6257; font-size: 13px; }
  label { display: block; font-weight: 600; font-size: 13px; margin: 14px 0 6px; }
  select, input[type="text"], input[type="date"], input[type="file"] {
    width: 100%; box-sizing: border-box; padding: 9px 10px; border: 1px solid #cfc6b8;
    border-radius: 8px; font-size: 14px; background: #fff;
  }
  button { margin-top: 20px; width: 100%; padding: 12px; border: 0; border-radius: 10px;
    background: #b3541e; color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; }
  button:disabled { opacity: .55; cursor: wait; }
  #status { margin-top: 14px; font-size: 13px; white-space: pre-wrap; word-break: break-word; }
  .err { color: #a11; }
  .row { display: flex; gap: 10px; }
  .row > div { flex: 1; }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>PDF Python Asli</h1>
    <p class="sub">PDF dibuat oleh generator Python asli (resi_merah3.py / laporan_final5.py / laporan_baru.py / laporan_shanghai.py) — persis seperti yang dijalankan Muse.</p>
    <form id="f">
      <label for="kind">Jenis laporan</label>
      <select id="kind">
        <option value="resi">Resi Merah (thermal 80×150mm)</option>
        <option value="full">Produksi Lengkap (PERKIRAAN)</option>
        <option value="baru">Produk Baru saja</option>
        <option value="shanghai">Shanghai saja</option>
      </select>
      <label for="csv">File CSV dari TikTok Seller Center</label>
      <input type="file" id="csv" accept=".csv" required>
      <div id="resiFields">
        <label for="tgl">Tanggal tampil (untuk Resi Merah)</label>
        <input type="text" id="tgl">
      </div>
      <div id="prodFields" style="display:none">
        <div class="row">
          <div>
            <label for="today">Tanggal acuan</label>
            <input type="date" id="today">
          </div>
          <div>
            <label for="stamp">Jam snapshot (HHMM)</label>
            <input type="text" id="stamp" maxlength="4">
          </div>
        </div>
      </div>
      <button type="submit" id="go">Buat PDF</button>
      <div id="status"></div>
    </form>
  </div>
</div>
<script>
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const now = new Date();
  const pad = n => String(n).padStart(2, "0");
  document.getElementById("tgl").value = now.getDate() + " " + MONTHS[now.getMonth()] + " " + now.getFullYear();
  document.getElementById("today").value = now.getFullYear() + "-" + pad(now.getMonth()+1) + "-" + pad(now.getDate());
  document.getElementById("stamp").value = pad(now.getHours()) + pad(now.getMinutes());
  const kind = document.getElementById("kind");
  function sync() {
    const isResi = kind.value === "resi";
    document.getElementById("resiFields").style.display = isResi ? "" : "none";
    document.getElementById("prodFields").style.display = isResi ? "none" : "";
  }
  kind.addEventListener("change", sync); sync();
  document.getElementById("f").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const status = document.getElementById("status");
    const btn = document.getElementById("go");
    const file = document.getElementById("csv").files[0];
    if (!file) { status.textContent = "Pilih file CSV dulu."; status.className = "err"; return; }
    let url;
    if (kind.value === "resi") {
      url = "/api/pdf/resi?tgl=" + encodeURIComponent(document.getElementById("tgl").value);
    } else {
      url = "/api/pdf/produksi?variant=" + encodeURIComponent(kind.value)
          + "&today=" + encodeURIComponent(document.getElementById("today").value)
          + "&stamp=" + encodeURIComponent(document.getElementById("stamp").value);
    }
    btn.disabled = true; status.className = ""; status.textContent = "Membuat PDF… (laporan produksi bisa 10–30 detik)";
    try {
      const buf = await file.arrayBuffer();
      const resp = await fetch(url, { method: "POST", body: buf });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error("Server menjawab " + resp.status + ":\n" + txt.slice(0, 2000));
      }
      const blob = await resp.blob();
      let fname = "laporan.pdf";
      const cd = resp.headers.get("Content-Disposition") || "";
      const m = cd.match(/filename="?([^"]+)"?/);
      if (m) fname = m[1];
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fname;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      status.textContent = "Selesai — PDF terunduh: " + fname;
    } catch (e) {
      status.className = "err";
      status.textContent = "Gagal: " + e.message;
    } finally {
      btn.disabled = false;
    }
  });
</script>
</body>
</html>"##;

// ---------------------------------------------------------------- pdf runs

fn month_num(m: &str) -> Option<u32> {
    match m {
        "Jan" => Some(1),
        "Feb" => Some(2),
        "Mar" => Some(3),
        "Apr" => Some(4),
        "May" => Some(5),
        "Jun" => Some(6),
        "Jul" => Some(7),
        "Aug" => Some(8),
        "Sep" => Some(9),
        "Oct" => Some(10),
        "Nov" => Some(11),
        "Dec" => Some(12),
        _ => None,
    }
}

fn resi_filename(tgl: &str) -> String {
    // "14 Nov 2026" -> RESI_MERAH_2026-11-14.pdf ; fallback RESI_MERAH.pdf
    let parts: Vec<&str> = tgl.split_whitespace().collect();
    if parts.len() == 3 {
        if let (Ok(day), Some(mon)) = (parts[0].parse::<u32>(), month_num(parts[1])) {
            return format!("RESI_MERAH_{}-{:02}-{:02}.pdf", parts[2], mon, day);
        }
    }
    "RESI_MERAH.pdf".to_string()
}

fn run_generator(
    script: &str,
    args: &[String],
    body: &[u8],
    out_name: &str,
) -> Result<(Vec<u8>, String), String> {
    let work = data_dir().join("work");
    fs::create_dir_all(&work).map_err(|e| e.to_string())?;
    fs::create_dir_all(data_dir().join("mplconfig")).map_err(|e| e.to_string())?;
    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let csv_path = work.join(format!("in-{ts}-{n}.csv"));
    let out_path = work.join(out_name);
    fs::write(&csv_path, body).map_err(|e| format!("tulis CSV gagal: {e}"))?;
    let script_path = scripts_dir().join(script);
    let py = python_cmd();
    let output = Command::new(&py)
        .arg(&script_path)
        .arg(&csv_path)
        .args(args)
        .arg(&out_path)
        .env("MPLCONFIGDIR", data_dir().join("mplconfig"))
        .env("PYTHONIOENCODING", "utf-8")
        .output()
        .map_err(|e| format!("gagal menjalankan python ({py}): {e}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    if output.status.success() && out_path.exists() {
        let pdf = fs::read(&out_path).map_err(|e| format!("baca PDF gagal: {e}"))?;
        let _ = fs::remove_file(&csv_path);
        let _ = fs::remove_file(&out_path);
        Ok((pdf, stdout))
    } else {
        let _ = fs::remove_file(&csv_path);
        Err(format!(
            "Generator {script} gagal (status {:?}).\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}",
            output.status.code()
        ))
    }
}

fn handle_pdf(stream: &mut TcpStream, req: &Request) -> io::Result<()> {
    if req.body.is_empty() {
        return respond_text(stream, "400 Bad Request", "Body kosong: kirim isi file CSV.");
    }
    let (script, args, filename): (&str, Vec<String>, String) = if req.path == "/api/pdf/resi" {
        let tgl = req
            .query
            .get("tgl")
            .cloned()
            .unwrap_or_else(|| "hari ini".to_string());
        (
            "resi_merah3.py",
            vec![tgl.clone()],
            resi_filename(&tgl),
        )
    } else {
        let variant = req
            .query
            .get("variant")
            .map(|s| s.as_str())
            .unwrap_or("full");
        let today = req.query.get("today").cloned().unwrap_or_default();
        let stamp = req.query.get("stamp").cloned().unwrap_or_default();
        if today.is_empty() || stamp.is_empty() {
            return respond_text(
                stream,
                "400 Bad Request",
                "Parameter today (YYYY-MM-DD) dan stamp (HHMM) wajib diisi.",
            );
        }
        let (script, prefix) = match variant {
            "baru" => ("laporan_baru.py", "PRODUK_BARU"),
            "shanghai" => ("laporan_shanghai.py", "SHANGHAI"),
            _ => ("laporan_final5.py", "PERKIRAAN_LAPORAN_PRODUKSI"),
        };
        (
            script,
            vec![today.clone(), stamp.clone()],
            format!("{prefix}_{today}_{stamp}.pdf"),
        )
    };
    match run_generator(script, &args, &req.body, &filename) {
        Ok((pdf, _stdout)) => {
            let cd = format!("Content-Disposition: attachment; filename=\"{filename}\"\r\n");
            respond(stream, "200 OK", "application/pdf", &pdf, &cd)
        }
        Err(msg) => respond_text(stream, "500 Internal Server Error", &msg),
    }
}

// ---------------------------------------------------------------- server

fn handle_conn(mut stream: TcpStream) {
    let req = match read_request(&mut stream) {
        Ok(Some(r)) => r,
        Ok(None) => return,
        Err(e) => {
            let _ = respond_text(&mut stream, "400 Bad Request", &format!("Request buruk: {e}"));
            return;
        }
    };
    let result = match (req.method.as_str(), req.path.as_str()) {
        ("GET", "/") => serve_app(&mut stream),
        ("GET", "/python-pdf") => respond(
            &mut stream,
            "200 OK",
            "text/html; charset=utf-8",
            BRIDGE_PAGE.as_bytes(),
            "",
        ),
        ("GET", "/api/ping") => respond(
            &mut stream,
            "200 OK",
            "application/json",
            br#"{"tokoops_exe":true}"#,
            "",
        ),
        ("POST", "/api/pdf/resi") | ("POST", "/api/pdf/produksi") => {
            handle_pdf(&mut stream, &req)
        }
        _ => respond_text(&mut stream, "404 Not Found", "Tidak ditemukan."),
    };
    if let Err(e) = result {
        eprintln!("[tokoops] response error: {e}");
    }
}

fn open_browser(url: &str) {
    #[cfg(windows)]
    {
        let _ = Command::new("cmd").args(["/C", "start", "", url]).spawn();
    }
    #[cfg(not(windows))]
    {
        println!("[tokoops] Buka di browser: {url}");
    }
}

fn main() {
    if let Err(e) = ensure_extracted() {
        eprintln!("[tokoops] PERINGATAN: ekstraksi awal gagal: {e}");
    }
    let mut listener: Option<TcpListener> = None;
    let mut port = 17654u16;
    for p in 17654..=17664 {
        match TcpListener::bind(("127.0.0.1", p)) {
            Ok(l) => {
                listener = Some(l);
                port = p;
                break;
            }
            Err(e) => {
                eprintln!("[tokoops] port {p} sibuk ({e}), coba berikutnya…");
            }
        }
    }
    let listener = match listener {
        Some(l) => l,
        None => {
            eprintln!("[tokoops] Tidak ada port bebas di 17654-17664. Keluar.");
            std::process::exit(1);
        }
    };
    let url = format!("http://127.0.0.1:{port}/");
    println!("[tokoops] TokoOps berjalan di {url}");
    open_browser(&url);
    for stream in listener.incoming() {
        match stream {
            Ok(s) => {
                std::thread::spawn(move || handle_conn(s));
            }
            Err(e) => eprintln!("[tokoops] accept error: {e}"),
        }
    }
}
