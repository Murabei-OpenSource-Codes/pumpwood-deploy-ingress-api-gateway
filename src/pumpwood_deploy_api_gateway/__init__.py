"""Kubernetes deployment package for the Pumpwood NGINX API gateway.

Provides two ingress variants for Pumpwood stacks:

- ``ApiGatewayCertbot`` — NGINX with Let's Encrypt HTTPS termination
  and a LoadBalancer Service.
- ``ApiGatewayNoCertificate`` — HTTP-only NGINX when TLS is handled
  upstream by a cloud load balancer.

Example:
    ```python
    from pumpwood_deploy.deploy import DeployPumpWood
    from pumpwood_deploy_api_gateway import (
        ApiGatewayCertbot, ApiGatewayNoCertificate)

    deploy.add_microservice(
        ApiGatewayNoCertificate(version="1.0"))
    ```

Use with ``DeployPumpWood`` from ``pumpwood-deploy``. The gateway
expects Kong (``load-balancer`` service) and application pods to be
deployed separately.
"""
from .deploy import (
    ApiGatewayCertbot, ApiGatewayNoCertificate)


__all__ = [
    ApiGatewayCertbot, ApiGatewayNoCertificate
]
