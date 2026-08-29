/**
 * Minimal QR Code encoder — byte mode, error-correction level M, versions 1–6.
 *
 * WHY THIS EXISTS
 * The exhibition screen needs to hand its own LAN URL to a judge's phone. That
 * is the only QR code in the product, so pulling in a QR dependency (and asking
 * the user to re-run `npm install` before the demo) is a poor trade. This is a
 * self-contained ~250-line encoder with no runtime dependencies.
 *
 * SCOPE — intentionally small
 *  - Byte mode only (a URL is ASCII/UTF-8), level M, versions 1–6.
 *  - Versions 1–6 need no version-information block, and at level M every block
 *    in those versions is the same length, which keeps interleaving trivial.
 *  - Capacity tops out at 106 bytes, far more than `http://192.168.x.x:3000/scan`.
 *    Longer input returns null, and the caller shows the plain URL instead of a
 *    broken code.
 *
 * Reference: ISO/IEC 18004. The format-information values are anchored against
 * the two published strings (L/mask0 = 111011111000100, M/mask0 = 101010000010010).
 */

// ---------------------------------------------------------------------------
// GF(256) arithmetic, primitive polynomial 0x11D
// ---------------------------------------------------------------------------
const EXP = new Uint8Array(512)
const LOG = new Uint8Array(256)

{
  let x = 1
  for (let i = 0; i < 255; i++) {
    EXP[i] = x
    LOG[x] = i
    x <<= 1
    if (x & 0x100) x ^= 0x11d
  }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255]
}

function gfMul(a: number, b: number): number {
  if (a === 0 || b === 0) return 0
  return EXP[LOG[a] + LOG[b]]
}

/** Coefficients (highest power first) of the RS generator for `degree` EC bytes. */
function rsGenerator(degree: number): Uint8Array {
  let poly = new Uint8Array([1])
  for (let d = 0; d < degree; d++) {
    const next = new Uint8Array(poly.length + 1)
    for (let i = 0; i < poly.length; i++) {
      next[i] ^= poly[i]
      next[i + 1] ^= gfMul(poly[i], EXP[d])
    }
    poly = next
  }
  return poly
}

/** Reed–Solomon check bytes for one block. */
function rsRemainder(data: Uint8Array, ecLen: number): Uint8Array {
  const gen = rsGenerator(ecLen)
  const buf = new Uint8Array(data.length + ecLen)
  buf.set(data)
  for (let i = 0; i < data.length; i++) {
    const factor = buf[i]
    if (factor === 0) continue
    for (let j = 0; j < gen.length; j++) buf[i + j] ^= gfMul(gen[j], factor)
  }
  return buf.slice(data.length)
}

// ---------------------------------------------------------------------------
// Version table (level M only). `total` = codewords in the symbol.
// v1..v3 are single-block; v4/v5 are two equal blocks; v6 is four equal blocks.
// ---------------------------------------------------------------------------
interface VersionSpec {
  version: number
  total: number
  blocks: number
  dataPerBlock: number
}

const SPECS: readonly VersionSpec[] = [
  { version: 1, total: 26, blocks: 1, dataPerBlock: 16 },
  { version: 2, total: 44, blocks: 1, dataPerBlock: 28 },
  { version: 3, total: 70, blocks: 1, dataPerBlock: 44 },
  { version: 4, total: 100, blocks: 2, dataPerBlock: 32 },
  { version: 5, total: 134, blocks: 2, dataPerBlock: 43 },
  { version: 6, total: 172, blocks: 4, dataPerBlock: 27 },
]

const PAD_BYTES = [0xec, 0x11] as const

/** Full codeword sequence (interleaved data + interleaved EC) for one symbol. */
function buildCodewords(bytes: Uint8Array, spec: VersionSpec): Uint8Array {
  const dataCount = spec.blocks * spec.dataPerBlock
  const ecPerBlock = spec.total / spec.blocks - spec.dataPerBlock

  // --- bit stream: mode (0100) + 8-bit length + payload -------------------
  const bits: number[] = []
  const push = (value: number, width: number) => {
    for (let i = width - 1; i >= 0; i--) bits.push((value >> i) & 1)
  }
  push(0b0100, 4)
  push(bytes.length, 8) // versions 1–9: byte-mode count is 8 bits
  // Indexed rather than `for..of`: the project targets ES5, where iterating a
  // typed array needs --downlevelIteration.
  for (let i = 0; i < bytes.length; i++) push(bytes[i], 8)

  // Terminator, then pad to a byte boundary, then alternating pad codewords.
  const capacityBits = dataCount * 8
  for (let i = 0; i < 4 && bits.length < capacityBits; i++) bits.push(0)
  while (bits.length % 8 !== 0) bits.push(0)

  const data = new Uint8Array(dataCount)
  for (let i = 0; i < bits.length; i += 8) {
    let byte = 0
    for (let j = 0; j < 8; j++) byte = (byte << 1) | bits[i + j]
    data[i / 8] = byte
  }
  for (let i = bits.length / 8, p = 0; i < dataCount; i++, p++) {
    data[i] = PAD_BYTES[p % 2]
  }

  // --- split into blocks, compute EC, interleave ---------------------------
  const dataBlocks: Uint8Array[] = []
  const ecBlocks: Uint8Array[] = []
  for (let b = 0; b < spec.blocks; b++) {
    const block = data.slice(b * spec.dataPerBlock, (b + 1) * spec.dataPerBlock)
    dataBlocks.push(block)
    ecBlocks.push(rsRemainder(block, ecPerBlock))
  }

  const out = new Uint8Array(spec.total)
  let k = 0
  for (let i = 0; i < spec.dataPerBlock; i++) {
    for (const block of dataBlocks) out[k++] = block[i]
  }
  for (let i = 0; i < ecPerBlock; i++) {
    for (const block of ecBlocks) out[k++] = block[i]
  }
  return out
}

// ---------------------------------------------------------------------------
// Symbol geometry
// ---------------------------------------------------------------------------
type Grid = { modules: boolean[][]; reserved: boolean[][]; size: number }

function newGrid(size: number): Grid {
  const modules = Array.from({ length: size }, () => new Array<boolean>(size).fill(false))
  const reserved = Array.from({ length: size }, () => new Array<boolean>(size).fill(false))
  return { modules, reserved, size }
}

/** Finder pattern (7×7) plus its separator, anchored at a top-left corner. */
function drawFinder(g: Grid, top: number, left: number) {
  for (let r = -1; r <= 7; r++) {
    for (let c = -1; c <= 7; c++) {
      const y = top + r
      const x = left + c
      if (y < 0 || x < 0 || y >= g.size || x >= g.size) continue
      const inRing = r >= 0 && r <= 6 && c >= 0 && c <= 6
      const dark =
        inRing &&
        (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4))
      g.modules[y][x] = dark
      g.reserved[y][x] = true
    }
  }
}

/** Alignment pattern (5×5) centred on (row, col). */
function drawAlignment(g: Grid, row: number, col: number) {
  for (let r = -2; r <= 2; r++) {
    for (let c = -2; c <= 2; c++) {
      g.modules[row + r][col + c] =
        Math.max(Math.abs(r), Math.abs(c)) !== 1 // dark ring, dark centre
      g.reserved[row + r][col + c] = true
    }
  }
}

function drawFunctionPatterns(g: Grid, version: number) {
  const size = g.size
  drawFinder(g, 0, 0)
  drawFinder(g, 0, size - 7)
  drawFinder(g, size - 7, 0)

  // Timing patterns (row 6 / column 6).
  for (let i = 0; i < size; i++) {
    if (!g.reserved[6][i]) {
      g.modules[6][i] = i % 2 === 0
      g.reserved[6][i] = true
    }
    if (!g.reserved[i][6]) {
      g.modules[i][6] = i % 2 === 0
      g.reserved[i][6] = true
    }
  }

  // Versions 2–6 carry exactly one alignment pattern, bottom-right.
  if (version >= 2) drawAlignment(g, size - 7, size - 7)

  // Reserve the two format-information areas.
  for (let i = 0; i <= 8; i++) {
    if (!g.reserved[8][i]) g.reserved[8][i] = true
    if (!g.reserved[i][8]) g.reserved[i][8] = true
  }
  for (let i = 0; i < 8; i++) {
    g.reserved[8][size - 1 - i] = true
    g.reserved[size - 1 - i][8] = true
  }

  // Dark module — always set, immediately above the lower format-info strip.
  g.modules[size - 8][8] = true
  g.reserved[size - 8][8] = true
}

/** Two-module-wide zigzag from the bottom-right, skipping function modules. */
function placeData(g: Grid, codewords: Uint8Array) {
  const size = g.size
  let bit = 0
  const nextBit = (): boolean => {
    const index = bit >> 3
    // Past the payload the remainder bits are light, as the spec requires.
    const value = index < codewords.length ? (codewords[index] >> (7 - (bit & 7))) & 1 : 0
    bit++
    return value === 1
  }

  let upward = true
  for (let right = size - 1; right >= 1; right -= 2) {
    // Column 6 is the timing pattern; the pair shifts one to the left.
    const col = right <= 6 ? right - 1 : right
    for (let i = 0; i < size; i++) {
      const row = upward ? size - 1 - i : i
      for (const c of [col, col - 1]) {
        if (c < 0 || g.reserved[row][c]) continue
        g.modules[row][c] = nextBit()
      }
    }
    upward = !upward
  }
}

const MASK_RULES: ReadonlyArray<(r: number, c: number) => boolean> = [
  (r, c) => (r + c) % 2 === 0,
  (r) => r % 2 === 0,
  (_r, c) => c % 3 === 0,
  (r, c) => (r + c) % 3 === 0,
  (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0,
  (r, c) => ((r * c) % 2) + ((r * c) % 3) === 0,
  (r, c) => (((r * c) % 2) + ((r * c) % 3)) % 2 === 0,
  (r, c) => (((r + c) % 2) + ((r * c) % 3)) % 2 === 0,
]

function applyMask(g: Grid, mask: number) {
  const rule = MASK_RULES[mask]
  for (let r = 0; r < g.size; r++) {
    for (let c = 0; c < g.size; c++) {
      if (!g.reserved[r][c] && rule(r, c)) g.modules[r][c] = !g.modules[r][c]
    }
  }
}

/**
 * 15-bit format information: 5 data bits (EC level M = 00, then the mask),
 * BCH(15,5) check bits with generator 0x537, whole word XOR 0x5412.
 */
function formatInfo(mask: number): number {
  const data = (0b00 << 3) | mask
  let rem = data << 10
  for (let i = 14; i >= 10; i--) {
    if (rem & (1 << i)) rem ^= 0x537 << (i - 10)
  }
  return ((data << 10) | rem) ^ 0x5412
}

/** Both copies of the format information. `bits[0]` is the most significant. */
function drawFormatInfo(g: Grid, mask: number) {
  const value = formatInfo(mask)
  const bits: boolean[] = []
  for (let i = 14; i >= 0; i--) bits.push(((value >> i) & 1) === 1)
  const size = g.size

  // Copy 1 — around the top-left finder.
  for (let i = 0; i <= 5; i++) g.modules[8][i] = bits[i]
  g.modules[8][7] = bits[6]
  g.modules[8][8] = bits[7]
  g.modules[7][8] = bits[8]
  for (let i = 9; i <= 14; i++) g.modules[14 - i][8] = bits[i]

  // Copy 2 — bottom-left column, then top-right row.
  for (let i = 0; i <= 6; i++) g.modules[size - 1 - i][8] = bits[i]
  for (let i = 7; i <= 14; i++) g.modules[8][size - 15 + i] = bits[i]
}

// ---------------------------------------------------------------------------
// Mask selection (ISO/IEC 18004 §8.8.2 penalty rules)
// ---------------------------------------------------------------------------
const FINDER_LIKE = [true, false, true, true, true, false, true]

function lineRuns(line: boolean[]): number {
  let penalty = 0
  let run = 1
  for (let i = 1; i < line.length; i++) {
    if (line[i] === line[i - 1]) {
      run++
    } else {
      if (run >= 5) penalty += 3 + (run - 5)
      run = 1
    }
  }
  if (run >= 5) penalty += 3 + (run - 5)
  return penalty
}

/** Rule 3: the finder-like 1:1:3:1:1 sequence with four light modules beside it. */
function finderLikePenalty(line: boolean[]): number {
  let penalty = 0
  for (let i = 0; i + 7 <= line.length; i++) {
    let core = true
    for (let k = 0; k < 7; k++) {
      if (line[i + k] !== FINDER_LIKE[k]) { core = false; break }
    }
    if (!core) continue
    const before = line.slice(Math.max(0, i - 4), i)
    const after = line.slice(i + 7, i + 11)
    const clear = (part: boolean[]) => part.length === 4 && part.every((m) => !m)
    if (clear(before) || clear(after)) penalty += 40
  }
  return penalty
}

function penalty(modules: boolean[][]): number {
  const size = modules.length
  let score = 0
  const columns: boolean[][] = Array.from({ length: size }, (_, c) =>
    modules.map((row) => row[c])
  )

  for (const line of modules) score += lineRuns(line) + finderLikePenalty(line)
  for (const line of columns) score += lineRuns(line) + finderLikePenalty(line)

  for (let r = 0; r < size - 1; r++) {
    for (let c = 0; c < size - 1; c++) {
      const m = modules[r][c]
      if (m === modules[r][c + 1] && m === modules[r + 1][c] && m === modules[r + 1][c + 1]) {
        score += 3
      }
    }
  }

  const dark = modules.reduce((sum, row) => sum + row.filter(Boolean).length, 0)
  const ratio = (dark * 100) / (size * size)
  score += Math.floor(Math.abs(ratio - 50) / 5) * 10
  return score
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export interface QrCode {
  /** Modules per side, excluding the quiet zone. */
  size: number
  /** `true` = dark. Indexed [row][column]. */
  modules: boolean[][]
  version: number
  mask: number
}

/** UTF-8 bytes. A LAN URL is ASCII, but this keeps the encoder honest. */
function utf8Bytes(text: string): Uint8Array {
  return new TextEncoder().encode(text)
}

/**
 * Encode `text` as a level-M QR code, choosing the smallest version that fits
 * and the lowest-penalty mask. Returns null when the text exceeds version 6
 * (106 bytes) — the caller should then show the URL as plain text.
 */
export function encodeQr(text: string): QrCode | null {
  const bytes = utf8Bytes(text)
  const spec = SPECS.find((s) => s.blocks * s.dataPerBlock * 8 >= 4 + 8 + bytes.length * 8)
  if (!spec) return null

  const codewords = buildCodewords(bytes, spec)
  const size = 17 + 4 * spec.version

  let best: QrCode | null = null
  let bestScore = Number.POSITIVE_INFINITY
  for (let mask = 0; mask < 8; mask++) {
    const g = newGrid(size)
    drawFunctionPatterns(g, spec.version)
    placeData(g, codewords)
    applyMask(g, mask)
    drawFormatInfo(g, mask)
    const score = penalty(g.modules)
    if (score < bestScore) {
      bestScore = score
      best = { size, modules: g.modules, version: spec.version, mask }
    }
  }
  return best
}

/** Flattened SVG path data for the dark modules, one module = one unit. */
export function qrPath(code: QrCode, quietZone = 4): string {
  const parts: string[] = []
  for (let r = 0; r < code.size; r++) {
    for (let c = 0; c < code.size; c++) {
      if (code.modules[r][c]) parts.push(`M${c + quietZone} ${r + quietZone}h1v1h-1z`)
    }
  }
  return parts.join('')
}
