"""Kubernetes deployment package for the Pumpwood NGINX API gateway.

Provides three ingress variants for Pumpwood stacks:

- ``ApiGatewayCertbot`` — NGINX with Let's Encrypt HTTPS termination
  and a LoadBalancer Service.
- ``ApiGatewayServerCertificate`` — NGINX with operator-managed TLS
  certificates mounted from a Kubernetes Secret.
- ``ApiGatewayNoCertificate`` — HTTP-only NGINX when TLS is handled
  upstream by a cloud load balancer.

Example:
    ```python
    from pumpwood_deploy.deploy import DeployPumpWood
    from pumpwood_deploy_api_gateway import (
        ApiGatewayServerCertificate)

    deploy.add_microservice(
        ApiGatewayServerCertificate(
            gateway_public_ip="203.0.113.10",
            version="4.3",
            server_name="app.example.com",
            certificate_crt_path="certs/certificate.crt",
            certificate_key_path="certs/certificate.key",
        ))
    ```

Use with ``DeployPumpWood`` from ``pumpwood-deploy``. The gateway
expects Kong (``load-balancer`` service) and application pods to be
deployed separately.

For Gandi or other external CAs, generate CSR and chain files with
``python -m pumpwood_deploy_api_gateway.tls_certificate``. See
``certs/README.md``.
"""
from .deploy import (
    ApiGatewayCertbot, ApiGatewayNoCertificate,
    ApiGatewayServerCertificate)


__all__ = [
    ApiGatewayCertbot, ApiGatewayNoCertificate,
    ApiGatewayServerCertificate
]
