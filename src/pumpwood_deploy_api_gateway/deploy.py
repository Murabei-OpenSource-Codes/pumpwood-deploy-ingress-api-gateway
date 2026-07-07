"""Kubernetes deployment manifests for the Pumpwood NGINX API gateway.

This module builds NGINX ingress manifests with CORS and security
headers for Pumpwood stacks. Three variants are available: Certbot with
Let's Encrypt HTTPS termination, server-provided TLS certificates from
a Kubernetes Secret, or HTTP-only when TLS is handled by a cloud load
balancer upstream.

Manifests are registered with ``DeployPumpWood.add_microservice`` from
``pumpwood-deploy``.
"""
import ipaddress
from importlib import resources
from jinja2 import Template
from pumpwood_deploy.abc import BasePumpwoodDeployMicroservice
from pumpwood_deploy.type import (
    PumpwoodDeploy, PumpwoodDeployService, PumpwoodDeployDeployment,
    PumpwoodDeploySecretFile)


nginx_gateway_deployment = resources\
    .files('pumpwood_deploy_api_gateway')\
    .joinpath('resources/deploy__nginx_certbot.yml')\
    .read_text(encoding='utf-8')
nginx_gateway_no_ssl_deployment = resources\
    .files('pumpwood_deploy_api_gateway')\
    .joinpath('resources/deploy__nginx_no_ssl.yml')\
    .read_text(encoding='utf-8')
external_service = resources\
    .files('pumpwood_deploy_api_gateway')\
    .joinpath('resources/service__external.yml')\
    .read_text(encoding='utf-8')
internal_service = resources\
    .files('pumpwood_deploy_api_gateway')\
    .joinpath('resources/service__internal.yml')\
    .read_text(encoding='utf-8')
nginx_certbot_pvc = resources\
    .files('pumpwood_deploy_api_gateway')\
    .joinpath('resources/pvc__nginx_certbot_letsencrypt.yml')\
    .read_text(encoding='utf-8')
nginx_server_certificate_deployment = resources\
    .files('pumpwood_deploy_api_gateway')\
    .joinpath('resources/deploy__nginx_server_certificate.yml')\
    .read_text(encoding='utf-8')


class ApiGatewayCertbot(BasePumpwoodDeployMicroservice):
    """Deploy NGINX API gateway with Certbot HTTPS termination.

    Renders an NGINX reverse proxy that adds CORS and security headers
    to Pumpwood applications and obtains TLS certificates from Let's
    Encrypt for the configured DNS name.

    A LoadBalancer Service is included. Private ``gateway_public_ip``
    values produce an internal load balancer; public values produce an
    external load balancer with optional source-range filtering.

    Example:
        ```python
        import os
        from pumpwood_deploy_api_gateway import ApiGatewayCertbot

        deploy.add_microservice(
            ApiGatewayCertbot(
                gateway_public_ip="203.0.113.10",
                email_contact="ops@example.com",
                version=os.getenv("API_GATEWAY_SSL"),
                server_name="app.example.com",
                repository="my-registry.example.com/",
                source_ranges=["203.0.113.0/24"],
            ))
        ```
    """

    def __init__(self, gateway_public_ip: str, email_contact: str,
                 version: str,
                 root_redirect_url: str = "admin/pumpwood-auth-app/gui/",
                 health_check_url: str = "health-check/pumpwood-auth-app/",
                 server_name: str = "not_set",
                 repository: str = "gcr.io/repositorio-geral-170012",
                 source_ranges: list[str] = ["0.0.0.0/0"]):
        """Initialize Certbot API gateway deployment configuration.

        Args:
            gateway_public_ip (str):
                Reserved IP for the LoadBalancer Service
                (``loadBalancerIP``). When the address is private, an
                internal load balancer manifest is rendered (GKE). When
                public, an external load balancer with source-range
                rules is rendered.
            email_contact (str):
                Contact email registered with Let's Encrypt for
                certificate issuance.
            version (str):
                Container image tag for ``pumpwood-nginx-ssl-gateway``.
            root_redirect_url (str):
                Path redirected when the root URL ``/`` is requested.
                Defaults to ``admin/pumpwood-auth-app/gui/``.
            health_check_url (str):
                Readiness probe path on port 80. Defaults to
                ``health-check/pumpwood-auth-app/``.
            server_name (str):
                DNS name passed to NGINX and Certbot. Defaults to
                ``not_set``.
            repository (str):
                Docker registry for the gateway image. Defaults to
                ``gcr.io/repositorio-geral-170012``.
            source_ranges (list[str]):
                CIDR blocks allowed to reach the external
                LoadBalancer. Defaults to ``["0.0.0.0/0"]`` (no
                restriction).
        """
        self.repository = repository
        self.gateway_public_ip = gateway_public_ip
        self.server_name = server_name
        self.email_contact = email_contact
        self.version = version
        self.health_check_url = health_check_url
        self.source_ranges = source_ranges
        self.root_redirect_url = root_redirect_url

    def create_deployment_file(self) -> list[PumpwoodDeploy]:
        """Build Kubernetes manifests for the Certbot API gateway.

        Returns:
            list[PumpwoodDeploy]:
                PVC ``nginx_certbot_gateway__letsencrypt_pvc``,
                Deployment ``nginx_certbot_gateway__deploy`` and
                Service ``nginx_certbot_gateway__endpoint``.
        """
        nginx_gateway_deployment__formated = nginx_gateway_deployment\
            .format(
                repository=self.repository,
                server_name=self.server_name,
                email_contact=self.email_contact,
                nginx_ssl_version=self.version,
                health_check_url=self.health_check_url,
                root_redirect_url=self.root_redirect_url)

        service__formated = None
        if ipaddress.ip_address(self.gateway_public_ip).is_private:
            service__formated = internal_service.format(
                public_ip=self.gateway_public_ip)
        else:
            external_service_template = Template(external_service)
            service__formated = external_service_template.render(
                public_ip=self.gateway_public_ip,
                firewall_ips=self.source_ranges)

        return [
            PumpwoodDeployDeployment(
                name='nginx_certbot_gateway__letsencrypt_pvc',
                content=nginx_certbot_pvc),
            PumpwoodDeployDeployment(
                name='nginx_certbot_gateway__deploy',
                content=nginx_gateway_deployment__formated),
            PumpwoodDeployService(
                name='nginx_certbot_gateway__endpoint',
                content=service__formated)
        ]


class ApiGatewayNoCertificate(BasePumpwoodDeployMicroservice):
    """Deploy NGINX API gateway without TLS termination.

    Renders an HTTP-only NGINX reverse proxy that adds CORS and
    security headers to Pumpwood applications. Use this variant when
    HTTPS is terminated upstream by a cloud vendor load balancer.

    Example:
        ```python
        import os
        from pumpwood_deploy_api_gateway import ApiGatewayNoCertificate

        deploy.add_microservice(
            ApiGatewayNoCertificate(
                version=os.getenv("API_GATEWAY"),
                health_check_url="health-check/pumpwood-auth-app/",
                target_service="load-balancer:8000",
                target_health="load-balancer:8001",
            ))
        ```
    """

    def __init__(self, version: str,
                 root_redirect_url: str = "admin/pumpwood-auth-app/gui/",
                 health_check_url: str = "health-check/pumpwood-auth-app/",
                 repository: str = "gcr.io/repositorio-geral-170012",
                 server_name: str = "localhost",
                 target_service: str = "load-balancer:8000",
                 target_health: str = "load-balancer:8001"):
        """Initialize HTTP-only API gateway deployment configuration.

        Args:
            version (str):
                Container image tag for ``pumpwood-nginx-without-ssl``.
            root_redirect_url (str):
                Path redirected when the root URL ``/`` is requested.
                Defaults to ``admin/pumpwood-auth-app/gui/``.
            health_check_url (str):
                Readiness probe path on port 80. Defaults to
                ``health-check/pumpwood-auth-app/``.
            repository (str):
                Docker registry for the gateway image. Defaults to
                ``gcr.io/repositorio-geral-170012``.
            server_name (str):
                ``server_name`` directive for NGINX. Defaults to
                ``localhost``.
            target_service (str):
                Upstream host for proxied traffic. Defaults to
                ``load-balancer:8000`` (Kong).
            target_health (str):
                Upstream host for health-check routing. Defaults to
                ``load-balancer:8001``.
        """
        self.root_redirect_url = root_redirect_url
        self.repository = repository
        self.version = version
        self.health_check_url = health_check_url
        self.server_name = server_name
        self.target_service = target_service
        self.target_health = target_health
        self.root_redirect_url = root_redirect_url

    def create_deployment_file(self) -> list[PumpwoodDeploy]:
        """Build Kubernetes manifest for the HTTP-only API gateway.

        Returns:
            list[PumpwoodDeploy]:
                Deployment ``nginx_no_ssl_gateway__deploy`` with embedded
                ClusterIP Service ``apigateway-nginx``. No external
                LoadBalancer is rendered; pair with a cloud ingress or
                load balancer as needed.
        """
        nginx_gateway_deployment__formated = \
            nginx_gateway_no_ssl_deployment.format(
                repository=self.repository,
                nginx_ssl_version=self.version,
                health_check_url=self.health_check_url,
                server_name=self.server_name,
                target_service=self.target_service,
                target_health=self.target_health,
                root_redirect_url=self.root_redirect_url)

        return [
            PumpwoodDeployDeployment(
                name='nginx_no_ssl_gateway__deploy',
                content=nginx_gateway_deployment__formated)]


class ApiGatewayServerCertificate(BasePumpwoodDeployMicroservice):
    """Deploy NGINX API gateway with operator-managed TLS certificates.

    Renders an NGINX reverse proxy that terminates HTTPS using
    certificate and private-key files supplied by the deployer. The
    files are uploaded to a Kubernetes Secret and mounted at
    ``/secrets`` inside the ``nginx-ssl-server-certificate`` image.

    Example:
        ```python
        import os
        from pumpwood_deploy_api_gateway import ApiGatewayServerCertificate

        deploy.add_microservice(
            ApiGatewayServerCertificate(
                gateway_public_ip="203.0.113.10",
                version=os.getenv("API_GATEWAY_SSL_SERVER"),
                server_name="app.example.com",
                certificate_crt_path="certs/certificate.crt",
                certificate_key_path="certs/certificate.key",
                repository="my-registry.example.com/",
            ))
        ```
    """

    def __init__(self, gateway_public_ip: str, version: str,
                 certificate_crt_path: str, certificate_key_path: str,
                 root_redirect_url: str = "admin/pumpwood-auth-app/gui/",
                 health_check_url: str = "health-check/pumpwood-auth-app/",
                 server_name: str = "not_set",
                 repository: str = "gcr.io/repositorio-geral-170012",
                 secret_name: str = "apigateway-nginx-ssl",
                 source_ranges: list[str] = ["0.0.0.0/0"]):
        """Initialize server-certificate API gateway deployment config.

        Args:
            gateway_public_ip (str):
                Reserved IP for the LoadBalancer Service
                (``loadBalancerIP``). When the address is private, an
                internal load balancer manifest is rendered (GKE). When
                public, an external load balancer with source-range
                rules is rendered.
            version (str):
                Container image tag for ``nginx-ssl-server-certificate``.
            certificate_crt_path (str):
                Local path to the TLS certificate file. The file name
                should be ``certificate.crt`` so the mounted Secret key
                matches the NGINX configuration.
            certificate_key_path (str):
                Local path to the TLS private key file. The file name
                should be ``certificate.key`` so the mounted Secret key
                matches the NGINX configuration.
            root_redirect_url (str):
                Path redirected when the root URL ``/`` is requested.
                Defaults to ``admin/pumpwood-auth-app/gui/``.
            health_check_url (str):
                Readiness probe path on port 80. Defaults to
                ``health-check/pumpwood-auth-app/``.
            server_name (str):
                DNS name passed to NGINX. Defaults to ``not_set``.
            repository (str):
                Docker registry for the gateway image. Defaults to
                ``gcr.io/repositorio-geral-170012``.
            secret_name (str):
                Kubernetes Secret name used to mount TLS files at
                ``/secrets``. Defaults to ``apigateway-nginx-ssl``.
            source_ranges (list[str]):
                CIDR blocks allowed to reach the external
                LoadBalancer. Defaults to ``["0.0.0.0/0"]`` (no
                restriction).
        """
        self.repository = repository
        self.gateway_public_ip = gateway_public_ip
        self.server_name = server_name
        self.version = version
        self.health_check_url = health_check_url
        self.source_ranges = source_ranges
        self.root_redirect_url = root_redirect_url
        self.secret_name = secret_name
        self.certificate_crt_path = certificate_crt_path
        self.certificate_key_path = certificate_key_path

    def create_deployment_file(self) -> list[PumpwoodDeploy]:
        """Build Kubernetes manifests for the server-certificate gateway.

        Returns:
            list[PumpwoodDeploy]:
                Secret file ``nginx_server_certificate_gateway__secret``,
                Deployment ``nginx_server_certificate_gateway__deploy`` and
                Service ``nginx_server_certificate_gateway__endpoint``.
        """
        nginx_gateway_deployment__formated = \
            nginx_server_certificate_deployment.format(
                repository=self.repository,
                server_name=self.server_name,
                nginx_ssl_version=self.version,
                health_check_url=self.health_check_url,
                root_redirect_url=self.root_redirect_url,
                secret_name=self.secret_name)

        service__formated = None
        if ipaddress.ip_address(self.gateway_public_ip).is_private:
            service__formated = internal_service.format(
                public_ip=self.gateway_public_ip)
        else:
            external_service_template = Template(external_service)
            service__formated = external_service_template.render(
                public_ip=self.gateway_public_ip,
                firewall_ips=self.source_ranges)

        return [
            PumpwoodDeploySecretFile(
                name=self.secret_name,
                path=[
                    self.certificate_crt_path,
                    self.certificate_key_path]),
            PumpwoodDeployDeployment(
                name='nginx_server_certificate_gateway__deploy',
                content=nginx_gateway_deployment__formated),
            PumpwoodDeployService(
                name='nginx_server_certificate_gateway__endpoint',
                content=service__formated)
        ]
