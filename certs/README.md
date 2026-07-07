# TLS files for ApiGatewayServerCertificate

Store operator-managed TLS material in this folder. Private keys and
issued certificates must **not** be committed to git.

## Generate key and CSR (Gandi step 1)

From the package root:

```bash
python -m pumpwood_deploy_api_gateway.tls_certificate generate-csr \
  --server-name app.example.com \
  --output-dir certs
```

Optional extra DNS names:

```bash
python -m pumpwood_deploy_api_gateway.tls_certificate generate-csr \
  --server-name app.example.com \
  --san www.app.example.com \
  --output-dir certs
```

Paste ``certs/request.csr`` into Gandi. Keep ``certs/certificate.key``
private.

## Build NGINX chain (Gandi step 2)

After Gandi returns the signed files, save them locally (for example
``gandi_domain.crt`` and ``gandi_intermediate.crt``), then run:

```bash
python -m pumpwood_deploy_api_gateway.tls_certificate build-chain \
  --leaf certs/gandi_domain.crt \
  --intermediate certs/gandi_intermediate.crt \
  --output certs/certificate.crt
```

## Deploy

```python
ApiGatewayServerCertificate(
    gateway_public_ip="203.0.113.10",
    version=os.getenv("API_GATEWAY_SSL_SERVER"),
    server_name="app.example.com",
    certificate_crt_path="certs/certificate.crt",
    certificate_key_path="certs/certificate.key",
)
```
