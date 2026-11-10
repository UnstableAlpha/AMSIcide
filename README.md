# AMSI Bypass Generator

A per-engagement PowerShell AMSI bypass generator for use during purple team and penetration testing engagements.

Each build produces a functionally identical but structurally unique bypass script, reducing the likelihood of static signature detection across engagements.

## Requirements

- Python 3.6 or later
- PyYAML: `pip install pyyaml`

## Files

| File | Purpose |
|------|---------|
| `build_bypass.py` | Build script |
| `engagement.yaml` | Engagement configuration |
| `bypass_output.ps1` | Generated output (created on run) |
| `README.md` | This file |

## Usage

```bash
python build_bypass.py --config engagement.yaml --output bypass_output.ps1
```

Both arguments are optional. Defaults are `engagement.yaml` and `bypass_output.ps1`.

## Configuration

All per-engagement settings are controlled via the YAML config file.

```yaml
engagement:
  client_id: ENG001
  domain: target.domain
  hostname: TARGET-HOST

bypass:
  xor_key: 67
  string_method: xor
  field_target: initfailed
  junk_var_count: 3

obfuscation:
  var_prefix: tmp
  case_randomise: true
```

### String methods

| Method | Description |
|--------|-------------|
| `xor` | XOR encodes target strings against the engagement key, decodes at runtime |
| `reverse` | Stores strings reversed, reconstructs at runtime |
| `chararray` | Builds strings from character code arrays at runtime |

Rotate the method and XOR key between engagements to produce structurally different output each time.

## Testing

Use a testing config with domain and hostname set to null and junk_var_count set to 0.

```yaml
engagement:
  client_id: TEST
  domain: null
  hostname: null

bypass:
  xor_key: 67
  string_method: xor
  field_target: initfailed
  junk_var_count: 0

obfuscation:
  var_prefix: tmp
  case_randomise: true
```

Run with:

```bash
python build_bypass.py --config testing.yaml --output test_bypass.ps1
```

On the test host, dot-source the generated script in an existing PowerShell session:

```powershell
. .\test_bypass.ps1
```

A successful bypass produces:

```
[+] Stage 1 passed: field set correctly
[+] Stage 2 passed: AMSI not scanning
```

A failed bypass produces one of:

```
[-] Stage 1 failed: field not set
[-] Stage 2 failed: AMSI blocked scan string - <error detail>
```

If Stage 1 fails, the script exits without running Stage 2.

## How it works

The bypass sets the `amsiInitFailed` field inside `System.Management.Automation.AmsiUtils`
to `true` via .NET reflection. When this field is true, PowerShell skips AMSI scanning
for that process entirely.

`[psobject]` is used as the assembly anchor. It lives in the same
`System.Management.Automation` assembly as `AmsiUtils`, so `.Assembly.GetType()` reaches
the correct target without requiring a dynamic type cast, which is not valid PowerShell syntax.

Every target string, including method names, binding flags, and the verification test string,
is encoded at build time and decoded at runtime. No plaintext tokens appear in the generated file.

## Verification

The generated script runs two verification stages after applying the bypass:

- Stage 1: Reads `amsiInitFailed` back via reflection and confirms the value is `true`
- Stage 2: Passes a known AMSI test string to a memory marshal call and confirms it is not intercepted

Both stages must pass for the bypass to be considered successful.

## Per-Engagement Variation

To generate a unique artefact per engagement, change the following before each build:

- `xor_key`: use a different integer value
- `string_method`: rotate between xor, reverse, and chararray
- `var_prefix`: use a short unique string
- `domain` and `hostname`: populate with target environment values
- `junk_var_count`: set to 2 or more to insert environment-keyed junk variables

## Notes

This tool is intended for use during authorised security engagements only. Ensure written
permission from the asset owner is in place before use. Test against your own EDR in a lab
environment before deploying on an engagement.

The verification output should be suppressed or redirected to your engagement logging layer
rather than left visible on screen during a real engagement.

ScriptBlock logging in a mature environment may still record script content after a successful
bypass. This is a separate defensive layer and is not addressed by this tool.