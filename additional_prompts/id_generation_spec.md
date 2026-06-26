# ID Generation Library for cbpr-validate

## Purpose

Build a deterministic, seedable ID generation library for the `cbpr-validate` tool so that `--example` output can produce realistic, structurally valid identifiers that pass the tool's own validation rules (XSD patterns + usage rules).

The library should be self-contained (no external dependencies beyond stdlib or a single lightweight PRNG), portable across languages (the spec is language-agnostic; Python is the reference), and deterministic when given the same seed.

---

## 1. Core PRNG: Counting Strings Algorithm

Do **not** use a language's built-in `random` or `uuid` module for production generation. Instead, implement the **Counting Strings** algorithm to produce deterministic, monotonically increasing pseudo-random-looking strings.

### Algorithm Specification

The Counting Strings algorithm treats a string as a base-N number where:

- **Alphabet**: `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz` (62 chars, index 0–61)
- A *string* is a sequence of characters from this alphabet.
- Counting proceeds by incrementing the rightmost character. When it wraps past the last alphabet character, it resets to `0` and the next position to the left increments (carry propagation).

```
0 -> 1 -> ... -> 9 -> A -> B -> ... -> Z -> a -> b -> ... -> z -> (carry) 00 -> 01 -> ...
```

### Reference Implementation (JavaScript-like pseudocode)

```javascript
const ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';

function countingString(seedStr) {
    // Convert seed string to array of indices
    let chars = seedStr.split('');
    let indices = chars.map(c => ALPHABET.indexOf(c));
    
    // Increment (add 1)
    let pos = indices.length - 1;
    while (pos >= 0) {
        indices[pos]++;
        if (indices[pos] >= ALPHABET.length) {
            indices[pos] = 0;
            pos--;
        } else {
            break;
        }
    }
    
    // If we carried past the front, prepend '0' (or handle length growth)
    if (pos < 0) {
        indices.unshift(0);
    }
    
    return indices.map(i => ALPHABET[i]).join('');
}

// Counter-based convenience: starts from a seed and increments
function countingSequence(seed, count) {
    let result = [];
    let current = seed;
    for (let i = 0; i < count; i++) {
        result.push(current);
        current = countingString(current);
    }
    return result;
}
```

### Use cases in this library

| Use | Approach |
|---|---|
| Deterministic "random" text | Use a **counter string** as seed, increment for each call |
| BIC location codes | 2-char counting strings seeded at `"00"` |
| IBAN BBAN filler | Pad the current counter value to the required length |
| LEI suffix | Counting string of appropriate length |
| Transaction reference numbers | Counting strings with application-specific prefixes |

---

## 2. IBAN Generation (ISO 13616)

### Background

IBAN = ISO 3166-1 country code (2 letters) + 2 check digits (ISO 7064 mod-97) + BBAN (Basic Bank Account Number, country-specific).

### Check Digit Algorithm (ISO 7064 mod-97)

```
function mod97CheckDigits(ibanWithoutCheckDigits):
    // ibanWithoutCheckDigits is country + "00" + bban
    rearranged = ibanWithoutCheckDigits[4:] + ibanWithoutCheckDigits[:4]
    numeric = ""
    for each char c in rearranged:
        if c is a letter:
            numeric += str(ord(c) - 55)   // A=10, B=11, ..., Z=35
        else:
            numeric += c
    checksum = 98 - (int(numeric) % 97)
    return twoDigitString(checksum)
```

### BBAN Patterns Per Country

The library MUST support generating valid BBANs for all 27 EU countries plus the ability to add more. Each country has a specific length and internal structure:

| Country | Code | IBAN Length | BBAN Pattern |
|---|---|---|---|
| Austria | AT | 20 | 5n 11n |
| Belgium | BE | 16 | 3n 7n 2n |
| Bulgaria | BG | 22 | 4a 4n 2n 4n 2n 4n (prefix BNBG) |
| Croatia | HR | 21 | 7n 10n |
| Cyprus | CY | 28 | 3a 5a 16a |
| Czechia | CZ | 24 | 4n 6n 10n |
| Denmark | DK | 18 | 4n 10n |
| Estonia | EE | 20 | 2n 2n 11n 1n |
| Finland | FI | 18 | 6n 8n |
| France | FR | 27 | 5n 5a 11a 2n |
| Germany | DE | 22 | 8n 10n |
| Greece | EL (not GR) | 27 | 7n 16n |
| Hungary | HU | 28 | 3n 4n 1n 15n 1n |
| Ireland | IE | 22 | 4a 6n 8n |
| Italy | IT | 27 | 1a 5n 5a 12n |
| Latvia | LV | 21 | 4a (BANK) 4n 11n |
| Lithuania | LT | 20 | 5n 11n |
| Luxembourg | LU | 20 | 3n 13n |
| Malta | MT | 31 | 4a (MALT) 4n 5n 18n |
| Netherlands | NL | 18 | 4a 10n |
| Poland | PL | 28 | 8n 16n |
| Portugal | PT | 25 | 4n 4n 11n 2n |
| Romania | RO | 24 | 4a (AAAA) 16n |
| Slovakia | SK | 24 | 4n 6n 10n |
| Slovenia | SI | 19 | 5n 8n 2n |
| Spain | ES | 24 | 4n 4n 2n 10n |
| Sweden | SE | 24 | 3n 16n 1n |

Key: `n` = digit, `a` = uppercase alphanumeric.

### Implementation Approach

```
function generateIBAN(countryCode, seedString):
    spec = lookupSpec(countryCode)
    length, pattern = spec
    bbanLength = length - 4
    
    // Build BBAN using counting strings seeded from the seed
    bban = ""
    for each segment in pattern (e.g. "5n" = 5 digits):
        if segment is fixed text:
            bban += fixedText
        elif segment type is 'n' (digits only):
            // Use counting string but map to digits only
            bban += takeN(countingSequence(seed, length), usingOnlyDigits)
        elif segment type is 'a' (alphanumeric):
            bban += takeN(countingSequence(seed, length), fullAlphabet)
    
    // Pad/truncate to exact bbanLength
    bban = bban[:bbanLength].ljust(bbanLength, '0')
    
    ibanPartial = countryCode + "00" + bban
    checksum = mod97CheckDigits(ibanPartial)
    return countryCode + checksum + bban
```

---

## 3. LEI Generation (ISO 17442)

### Structure

- 20 characters total
- Characters 1–18: LOU prefix (6 chars) + reserved/alphanumeric (12 chars) = 18 chars
- Characters 19–20: ISO 7064 mod-97 check digits

### LOU Prefixes (well-known)

| LOU | Prefix |
|---|---|
| WM Datenservice | 529900 |
| Bloomberg | 549300 |
| LSE | 213800 |
| DTCC | 254900 |
| INSEE | 969500 |
| GLEIF | 391200 |
| CB | 097900 |
| NSD | 315700 |
| AECMA | 875500 |
| CICI | 485100 |

### Algorithm

```
function generateLEI(seedString):
    prefix = pickDeterministicFromSeed(LOU_PREFIXES, seedString)
    suffixLength = 18 - len(prefix)
    suffix = countingSequence(seedString, suffixLength)  // alphanumeric
    
    leiWithoutCS = (prefix + suffix).ljust(18, '0')[:18]
    
    // Compute mod-97 check digits (same algorithm as IBAN)
    digits = ""
    for each char c in (leiWithoutCS + "00"):
        if c is letter: digits += str(ord(c) - 55)
        else: digits += c
    
    checksum = 98 - (int(digits) % 97)
    
    return leiWithoutCS + twoDigitString(checksum)
```

XSD pattern: `[A-Z0-9]{18,18}[0-9]{2,2}`

---

## 4. BIC Generation (ISO 9362)

### Structure

BIC = 4-char bank code + 2-char country code + 2-char location code [+ 3-char branch code]

XSD pattern: `[A-Z0-9]{4,4}[A-Z]{2,2}[A-Z0-9]{2,2}([A-Z0-9]{3,3}){0,1}`

### Algorithm

```
function generateBIC(bankCode, countryCode, branchCode="XXX", seedString):
    bank = padOrTruncate(bankCode, 4)    // uppercase, pad with X
    country = countryCode.upper()[:2]
    
    // Location code from counting string (2 chars, seeded)
    loc = countingString(seedString)[:2].toUpperCase()
    // Ensure location code matches [A-Z0-9]{2}
    loc = sanitizeToAlphanumeric(loc, 2)
    
    if branchCode:
        branch = branchCode.upper()[:3]
        return bank + country + loc + branch
    else:
        return bank + country + loc
```

### Usage

Pre-register known BIC mappings for common test banks:

| Bank | BIC |
|---|---|
| John Smith's Bank PLC (GB) | JSBPGB2LXXX |
| Bank Austria | BANKATZZXXX |
| Deutsche Bank | DEUTDEFFXXX |
| BNP Paribas | BNPAPARBXXX |

For --example output, generate from a seed so output is stable.

---

## 5. UUID v4 / UETR Generation

### Structure

Standard RFC 4122 UUID v4: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx` where `x` is random hex and `y` is `[89ab]`.

### Counting-String-Based Approach

Since we want deterministic output, do NOT use `uuid.uuid4()`. Instead:

```
function generateUUID(counter):
    // Use the counting string to fill the 32 hex characters
    hexChars = countingSequence("00000000000000000000000000000000", counter + 1)[counter]
    
    // Ensure version nibble is 4 at position 12
    hexChars = hexChars[:12] + "4" + hexChars[13:]
    
    // Ensure variant is RFC 4122 (10xx) at position 16
    variantNibble = int(hexChars[16], 16)
    variantNibble = (variantNibble & 0x3) | 0x8  // set top 2 bits to 10
    hexChars = hexChars[:16] + hexChars[17:]  // rebuild
    
    return formatUUID(hexChars)  // insert dashes at 8-4-4-12
```

Alternative: use a simple integer counter and format as UUID:

```
function uuidFromCounter(counter):
    hex = formatInt(counter, '032x')
    hex = hex[:12] + '4' + hex[13:]
    hex = hex[:16] + hex[17:]
    // variant
    return insertDashes(hex)
```

The UETR field in ISO 20022 is exactly a UUID v4.

---

## 6. MID / Message Identifier Generation

### Purpose

Generate unique, deterministic message identifiers for test messages:

- `BizMsgIdr` (AppHdr)
- `MsgId` (GroupHeader) 
- `InstrId`
- `EndToEndId`
- `TxId`

### Format Convention

Use a consistent scheme:

```
{PREFIX}{COUNTER_STRING}
```

Where:

| Field | Prefix | Example |
|---|---|---|
| BizMsgIdr / MsgId | `CBPR{CC}` | `CBPRAT2026001` |
| InstrId | `INST{CC}` | `INSTAT001` |
| EndToEndId | `E2E{CC}` | `E2EAT001` |
| UETR | (UUID) | `a1b2c3d4-...` |

The `{CC}` is the 2-letter ISO country code. The counter can be a counting string or simple integer.

### Function

```
function generateMID(prefix, countryCode, counter):
    cc = countryCode.upper()[:2]
    countStr = toCountingBase(counter, 6)  // 6-char zero-padded
    return prefix + cc + countStr
```

---

## 7. Random Text / Number Utilities

### deterministicInt(seed, min, max)

Given a counting-string seed, produce a deterministic integer in range:

```
function deterministicInt(seed, min, max):
    // Use the counting string's numeric value modulo range
    numericValue = sum of (alphabetIndex(c) * (62 ^ position)) for each char c in seed
    return min + (numericValue % (max - min + 1))
```

### deterministicChoice(seed, items)

Choose deterministically from a list:

```
return items[deterministicInt(seed, 0, len(items) - 1)]
```

### deterministicString(seed, length, characterSet)

```
result = ""
for i in range(length):
    pos = deterministicInt(seed + str(i), 0, len(characterSet) - 1)
    result += characterSet[pos]
return result
```

### ISO Date/Time Helpers

```
function todayISO():
    return currentDateInUTC().format("YYYY-MM-DD")

function nowISO():
    return currentDateTimeInUTC().format("YYYY-MM-DDTHH:MM:SS+00:00")
```

---

## 8. Input / Output Specification

### Global Seed

The library should accept a single global seed string (e.g. `"example001"`) that deterministically controls all generated output. Every function should be deterministic given the seed.

### Function Signatures (Python reference)

```python
# ---- Core ----
def counting_string(s: str) -> str
def counting_sequence(seed: str, count: int) -> list[str]

# ---- IBAN ----
def generate_iban(country: str, seed: str = "") -> str

# ---- LEI ----
def generate_lei(seed: str = "") -> str

# ---- BIC ----
def generate_bic(bank_code: str | None = None,
                 country: str = "GB",
                 branch: str = "XXX",
                 seed: str = "") -> str

# ---- UUID ----
def generate_uuid(counter: int = 0) -> str
def generate_uetr(counter: int = 0) -> str

# ---- MID ----
def generate_mid(prefix: str, country: str, counter: int) -> str

# ---- Utilities ----
def deterministic_int(seed: str, min: int, max: int) -> int
def deterministic_choice(seed: str, items: list) -> Any
def deterministic_string(seed: str, length: int,
                         charset: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") -> str

# ---- Date ----
def today_iso() -> str
def now_iso() -> str
```

### CLI Integration

The `cbpr-validate --example` command should use this library internally:

```
cbpr-validate --year 2026 --type pacs.008 --example min
# Internally calls id_generator with seed="min_2026_pacs008"
```

---

## 9. Validation / Test Requirements

The generated IDs must pass the tool's own validation:

| ID Type | XSD Pattern |
|---|---|
| BIC | `[A-Z0-9]{4,4}[A-Z]{2,2}[A-Z0-9]{2,2}([A-Z0-9]{3,3}){0,1}` |
| LEI | `[A-Z0-9]{18,18}[0-9]{2,2}` |
| IBAN | `[A-Z]{2,2}[0-9]{2,2}[a-zA-Z0-9]{1,30}` (varies by country length) |
| Country | ISO 3166-1 alpha-2 |
| Currency | ISO 4217 (active) |
| UUID | RFC 4122 format |

### Self-Test

The library MUST include a self-test that:
1. Generates one IBAN for each supported country
2. Verifies mod-97 checksum for each
3. Generates 3 LEIs and verifies check digits
4. Generates BICs and validates against the XSD pattern
5. Generates UUIDs and validates the version nibble (must be `4`)
6. Runs all examples with deterministic output (same seed → same result)

---

## 10. Integration Points in cbpr-validate

The id generation library is consumed in two places:

1. **`--example` flag**: When generating example XML messages (both `min` and `max`), every placeholder value should use the ID generation library instead of hardcoded strings like `EXMsgId`.

2. **New `--generate` subcommand** (optional enhancement): 
   ```
   cbpr-validate --generate iban AT
   cbpr-validate --generate lei
   cbpr-validate --generate bic JSBP GB
   ```

### Seed Convention

| Context | Seed |
|---|---|
| `--example min --year 2026 --type pacs.008` | `min_2026_pacs008` |
| `--example max --year 2026 --type pacs.008` | `max_2026_pacs008` |
| Individual `--generate iban AT` | (current datetime hash) |
