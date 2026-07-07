"""Helpers to prepare TLS files for ApiGatewayServerCertificate.

Use this module when certificates are issued by an external CA such as
Gandi. It generates a private key and CSR, then builds the NGINX
``certificate.crt`` chain after the CA returns the signed files.

Example:
    ```bash
    python -m pumpwood_deploy_api_gateway.tls_certificate generate-csr \\
        --server-name app.example.com \\
        --output-dir certs

    # Paste certs/request.csr into Gandi, download the signed PEM files,
    # then build the chain for deploy:

    python -m pumpwood_deploy_api_gateway.tls_certificate build-chain \\
        --leaf certs/gandi_domain.crt \\
        --intermediate certs/gandi_intermediate.crt \\
        --output certs/certificate.crt
    ```
"""
import argparse
import os
import stat
import subprocess
import sys


DEFAULT_KEY_NAME = 'certificate.key'
DEFAULT_CSR_NAME = 'request.csr'
DEFAULT_CERT_NAME = 'certificate.crt'
DEFAULT_OPENSSL_CONFIG_NAME = 'openssl.cnf'


class TlsCertificateError(Exception):
    """Raised when OpenSSL TLS file generation fails."""


def _run_openssl(args):
    """Run an OpenSSL command and raise on failure.

    Args:
        args (list):
            OpenSSL command arguments without the ``openssl`` binary name.

    Returns:
        None:
            Always returns None when the command succeeds.

    Raises:
        TlsCertificateError:
            If OpenSSL exits with a non-zero status.
    """
    command = ['openssl'] + args
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False)
    if process.returncode != 0:
        stderr_text = process.stderr.decode('utf-8', errors='replace').strip()
        message = 'OpenSSL command failed: {command}\n{stderr}'.format(
            command=' '.join(command),
            stderr=stderr_text)
        raise TlsCertificateError(message)


def _write_openssl_config(server_name, san_names, config_path):
    """Write an OpenSSL config file with CN and SAN entries.

    Args:
        server_name (str):
            Common Name placed in the certificate subject.
        san_names (list):
            DNS names listed as subjectAltName entries.
        config_path (str):
            Destination path for the OpenSSL configuration file.

    Returns:
        None:
            Always returns None.
    """
    if not san_names:
        san_names = [server_name]

    alt_names_lines = []
    for index, dns_name in enumerate(san_names, start=1):
        alt_names_lines.append(
            'DNS.{index} = {dns_name}'.format(
                index=index, dns_name=dns_name))

    alt_names_block = '\n'.join(alt_names_lines)
    config_text = (
        '[ req ]\n'
        'default_bits = 4096\n'
        'prompt = no\n'
        'default_md = sha256\n'
        'distinguished_name = req_distinguished_name\n'
        'req_extensions = v3_req\n'
        '\n'
        '[ req_distinguished_name ]\n'
        'CN = {server_name}\n'
        '\n'
        '[ v3_req ]\n'
        'subjectAltName = @alt_names\n'
        '\n'
        '[ alt_names ]\n'
        '{alt_names_block}\n'
    ).format(
        server_name=server_name,
        alt_names_block=alt_names_block)

    with open(config_path, 'w', encoding='utf-8') as config_file:
        config_file.write(config_text)


def _restrict_private_key_permissions(key_path):
    """Restrict private key permissions to owner read/write on Unix.

    Args:
        key_path (str):
            Path to the generated private key file.

    Returns:
        None:
            Always returns None.
    """
    if os.name != 'posix':
        return
    current_mode = os.stat(key_path).st_mode
    os.chmod(
        key_path,
        (current_mode & ~stat.S_IRWXG & ~stat.S_IRWXO)
        | stat.S_IRUSR
        | stat.S_IWUSR)


def generate_csr_and_key(server_name,
                         output_dir='certs',
                         key_name=DEFAULT_KEY_NAME,
                         csr_name=DEFAULT_CSR_NAME,
                         key_bits=4096,
                         san_names=None):
    """Generate a private key and CSR for an external certificate authority.

    The output file names match ``ApiGatewayServerCertificate`` defaults.
    Submit ``request.csr`` to Gandi or another CA. Keep ``certificate.key``
    private; it is required again when building the final deploy files.

    Args:
        server_name (str):
            DNS name used as CN and as the first subjectAltName entry.
        output_dir (str):
            Directory where key, CSR, and OpenSSL config are written.
            Defaults to ``certs``.
        key_name (str):
            Private key file name inside ``output_dir``. Defaults to
            ``certificate.key``.
        csr_name (str):
            CSR file name inside ``output_dir``. Defaults to
            ``request.csr``.
        key_bits (int):
            RSA key size passed to OpenSSL. Defaults to ``4096``.
        san_names (list | None):
            Optional extra DNS subjectAltName values. ``server_name`` is
            always included. Defaults to None.

    Returns:
        dict:
            Mapping with absolute paths for ``key_path``, ``csr_path``,
            and ``config_path``.

    Raises:
        TlsCertificateError:
            If OpenSSL key or CSR generation fails.
        OSError:
            If ``output_dir`` cannot be created or files cannot be written.
    """
    if not server_name or not server_name.strip():
        raise TlsCertificateError('server_name must not be empty')

    os.makedirs(output_dir, exist_ok=True)

    key_path = os.path.join(output_dir, key_name)
    csr_path = os.path.join(output_dir, csr_name)
    config_path = os.path.join(output_dir, DEFAULT_OPENSSL_CONFIG_NAME)

    if san_names is None:
        dns_names = [server_name]
    else:
        dns_names = [server_name]
        for dns_name in san_names:
            if dns_name not in dns_names:
                dns_names.append(dns_name)

    _write_openssl_config(
        server_name=server_name,
        san_names=dns_names,
        config_path=config_path)

    _run_openssl([
        'genrsa',
        '-out', key_path,
        str(key_bits),
    ])
    _restrict_private_key_permissions(key_path)

    _run_openssl([
        'req',
        '-new',
        '-key', key_path,
        '-out', csr_path,
        '-config', config_path,
    ])

    return {
        'key_path': os.path.abspath(key_path),
        'csr_path': os.path.abspath(csr_path),
        'config_path': os.path.abspath(config_path),
    }


def build_certificate_chain(leaf_path,
                            output_path,
                            intermediate_paths=None):
    """Build an NGINX PEM chain from leaf and intermediate certificates.

    Args:
        leaf_path (str):
            Path to the domain certificate issued by the CA.
        output_path (str):
            Destination path for ``certificate.crt``.
        intermediate_paths (list | None):
            Optional intermediate CA certificate paths appended after the
            leaf certificate. Defaults to None.

    Returns:
        str:
            Absolute path to the generated ``certificate.crt`` file.

    Raises:
        TlsCertificateError:
            If any input certificate file is missing.
        OSError:
            If the output file cannot be written.
    """
    if not os.path.isfile(leaf_path):
        message = 'Leaf certificate file not found: {path}'.format(
            path=leaf_path)
        raise TlsCertificateError(message)

    certificate_paths = [leaf_path]
    if intermediate_paths:
        for intermediate_path in intermediate_paths:
            if not os.path.isfile(intermediate_path):
                message = (
                    'Intermediate certificate file not found: {path}'
                ).format(path=intermediate_path)
                raise TlsCertificateError(message)
            certificate_paths.append(intermediate_path)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    chain_parts = []
    for certificate_path in certificate_paths:
        with open(certificate_path, 'r', encoding='utf-8') as cert_file:
            chain_parts.append(cert_file.read().strip())

    chain_text = '\n\n'.join(chain_parts) + '\n'
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(chain_text)

    return os.path.abspath(output_path)


def _command_generate_csr(args):
    """Run the ``generate-csr`` CLI command.

    Args:
        args (argparse.Namespace):
            Parsed command-line arguments.

    Returns:
        int:
            Process exit code. Returns ``0`` on success.

    Raises:
        TlsCertificateError:
            Propagated from :func:`generate_csr_and_key`.
    """
    san_names = args.san or None
    result = generate_csr_and_key(
        server_name=args.server_name,
        output_dir=args.output_dir,
        key_bits=args.key_bits,
        san_names=san_names)

    print('Private key: {key_path}'.format(key_path=result['key_path']))
    print('CSR file: {csr_path}'.format(csr_path=result['csr_path']))
    print('OpenSSL config: {config_path}'.format(
        config_path=result['config_path']))
    print('')
    print('Next steps:')
    print('1. Paste the CSR into Gandi or your certificate provider.')
    print('2. Keep certificate.key private and out of version control.')
    print('3. After issuance, run build-chain to create certificate.crt.')
    return 0


def _command_build_chain(args):
    """Run the ``build-chain`` CLI command.

    Args:
        args (argparse.Namespace):
            Parsed command-line arguments.

    Returns:
        int:
            Process exit code. Returns ``0`` on success.

    Raises:
        TlsCertificateError:
            Propagated from :func:`build_certificate_chain`.
    """
    output_path = build_certificate_chain(
        leaf_path=args.leaf,
        output_path=args.output,
        intermediate_paths=args.intermediate)

    print('NGINX certificate chain: {output_path}'.format(
        output_path=output_path))
    print('')
    print('Deploy with ApiGatewayServerCertificate using:')
    print('  certificate_crt_path="{output_path}"'.format(
        output_path=output_path))
    key_path = os.path.join(
        os.path.dirname(output_path),
        DEFAULT_KEY_NAME)
    print('  certificate_key_path="{key_path}"'.format(
        key_path=key_path))
    return 0


def _build_parser():
    """Build the command-line argument parser.

    Returns:
        argparse.ArgumentParser:
            Parser configured with TLS helper subcommands.
    """
    parser = argparse.ArgumentParser(
        description=(
            'Generate TLS files for ApiGatewayServerCertificate.'))
    subparsers = parser.add_subparsers(dest='command')

    generate_parser = subparsers.add_parser(
        'generate-csr',
        help='Create certificate.key and request.csr for an external CA.')
    generate_parser.add_argument(
        '--server-name',
        required=True,
        help='DNS name used as CN and primary subjectAltName.')
    generate_parser.add_argument(
        '--output-dir',
        default='certs',
        help='Directory for generated files. Defaults to certs.')
    generate_parser.add_argument(
        '--key-bits',
        type=int,
        default=4096,
        help='RSA key size. Defaults to 4096.')
    generate_parser.add_argument(
        '--san',
        action='append',
        default=[],
        help='Extra DNS subjectAltName. Repeat for multiple names.')
    generate_parser.set_defaults(func=_command_generate_csr)

    chain_parser = subparsers.add_parser(
        'build-chain',
        help='Build certificate.crt from CA-issued PEM files.')
    chain_parser.add_argument(
        '--leaf',
        required=True,
        help='Path to the domain certificate issued by the CA.')
    chain_parser.add_argument(
        '--intermediate',
        action='append',
        default=[],
        help='Intermediate CA certificate path. Repeat if needed.')
    chain_parser.add_argument(
        '--output',
        default=os.path.join('certs', DEFAULT_CERT_NAME),
        help='Output path for certificate.crt.')
    chain_parser.set_defaults(func=_command_build_chain)

    return parser


def main(argv=None):
    """Entry point for the TLS certificate helper CLI.

    Args:
        argv (list | None):
            Optional argument list. Defaults to ``sys.argv[1:]``.

    Returns:
        int:
            Process exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except TlsCertificateError as error:
        print('Error: {message}'.format(message=error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
