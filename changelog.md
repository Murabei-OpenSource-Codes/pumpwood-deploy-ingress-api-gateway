# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-07-07

### Added

- **`ApiGatewayServerCertificate`**: NGINX gateway with operator-managed TLS
  certificates mounted from a Kubernetes Secret via
  ``PumpwoodDeploySecretFile``.
- **`tls_certificate` CLI module** (`python -m
  pumpwood_deploy_api_gateway.tls_certificate`):
  - ``generate-csr`` — create ``certificate.key`` and ``request.csr`` for
    external CAs (Gandi, corporate PKI).
  - ``build-chain`` — assemble ``certificate.crt`` PEM chain for NGINX.
- **`deploy__nginx_server_certificate.yml`**: Deployment manifest for the
  ``nginx-ssl-server-certificate`` image.
- **`pvc__nginx_certbot_letsencrypt.yml`**: PersistentVolumeClaim for
  Certbot / Let's Encrypt certificate storage.
- **`certs/`** directory with ``README.md``, ``.gitkeep``, and
  ``.gitignore`` rules to keep private TLS material out of version control.

### Changed

- **`ApiGatewayCertbot`**: mounts the Let's Encrypt PVC at
  ``/etc/letsencrypt`` and registers manifest
  ``nginx_certbot_gateway__letsencrypt_pvc``.
- **`README.md`**: added Option C (Gandi / external CA), configuration
  reference for ``ApiGatewayServerCertificate``, and
  ``API_GATEWAY_SSL_SERVER`` environment variable.
- **Module docstrings**: updated package and deploy module docs for the
  third ingress variant.

### Removed

- No removes.

## [0.0.1] - 2026-06-16

### Added

- Initial satellite package for Pumpwood NGINX API gateway deployments on
  Kubernetes, extracted from the monolithic ``pumpwood-deploy`` package.
- **`ApiGatewayCertbot`**: NGINX with Let's Encrypt HTTPS termination and
  external or internal LoadBalancer Service.
- **`ApiGatewayNoCertificate`**: HTTP-only NGINX when TLS is handled
  upstream (AWS ALB, GCP LB, etc.). Replaces ``CORSTerminaton`` from
  ``pumpwood_deploy.microservices.api_gateway.deploy``.
- Kubernetes resource templates:
  - ``deploy__nginx_certbot.yml``
  - ``deploy__nginx_no_ssl.yml``
  - ``service__external.yml``
  - ``service__internal.yml``
- Project scaffolding: ``build.sh``, ``pyproject.toml``,
  ``README.md``, ``LICENSE``, and generated API documentation under
  ``docs/``.

### Changed

- No changes.

### Removed

- No removes.
