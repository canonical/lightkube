import json
import os
import ssl
import subprocess
from typing import Optional
import asyncio.subprocess

import httpx

from .kubeconfig import SingleConfig
from .models import Cluster, User, UserExec, FileStr
from ..core.exceptions import ConfigError


def Client(
    config: SingleConfig,
    timeout: httpx.Timeout,
    trust_env: bool = True,
    transport: httpx.BaseTransport = None,
    proxy: str = None,
) -> httpx.Client:
    return httpx.Client(
        transport=transport, **httpx_parameters(config, timeout, proxy, trust_env)
    )


def AsyncClient(
    config: SingleConfig,
    timeout: httpx.Timeout,
    trust_env: bool = True,
    transport: httpx.AsyncBaseTransport = None,
    proxy: str = None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=transport, **httpx_parameters(config, timeout, proxy, trust_env)
    )


def httpx_parameters(config: SingleConfig, timeout: httpx.Timeout, proxy: str, trust_env: bool):
    return dict(
        timeout=timeout,
        proxy=proxy,
        base_url=config.cluster.server,
        verify=verify_cluster(config.cluster, config.user, config.abs_file, trust_env=trust_env),
        auth=user_auth(config.user),
        trust_env=trust_env,
    )


class BearerAuth(httpx.Auth):
    def __init__(self, token):
        self._bearer = f"Bearer {token}"

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = self._bearer
        yield request


async def async_check_output(command, env):
    PIPE = asyncio.subprocess.PIPE
    proc = await asyncio.create_subprocess_exec(
        *command, env=env, stdin=None, stdout=PIPE, stderr=PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ConfigError(
            f"Exec {command[0]} returned {proc.returncode}: {stderr.decode()}"
        )
    return stdout


def sync_check_output(command, env):
    proc = subprocess.Popen(
        command, env=env, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise ConfigError(
            f"Exec {command[0]} returned {proc.returncode}: {stderr.decode()}"
        )
    return stdout


class ExecAuth(httpx.Auth):
    def __init__(self, exec: UserExec):
        self._exec = exec
        self._last_bearer = None

    def _prepare(self):
        exec = self._exec
        if exec.apiVersion not in (
            "client.authentication.k8s.io/v1alpha1",
            "client.authentication.k8s.io/v1beta1",
        ):
            raise ConfigError(
                f"auth exec api version {exec.apiVersion} not implemented"
            )
        cmd_env_vars = dict(os.environ)
        if exec.env:
            cmd_env_vars.update((var.name, var.value) for var in exec.env)
        # TODO: add support for passing KUBERNETES_EXEC_INFO env var
        # https://github.com/kubernetes/community/blob/master/contributors/design-proposals/auth/kubectl-exec-plugins.md
        args = exec.args if exec.args else []
        return [exec.command] + args, cmd_env_vars

    def sync_auth_flow(self, request: httpx.Request):
        if self._last_bearer:
            request.headers["Authorization"] = self._last_bearer
            response = yield request
            if response.status_code != 401:
                return

        command, env = self._prepare()
        output = sync_check_output(command, env=env)
        token = json.loads(output)["status"]["token"]
        request.headers["Authorization"] = self._last_bearer = f"Bearer {token}"
        yield request

    async def async_auth_flow(self, request: httpx.Request):
        if self._last_bearer:
            request.headers["Authorization"] = self._last_bearer
            response = yield request
            if response.status_code != 401:
                return

        command, env = self._prepare()
        output = await async_check_output(command, env=env)
        token = json.loads(output)["status"]["token"]
        request.headers["Authorization"] = self._last_bearer = f"Bearer {token}"
        yield request


def user_auth(user: Optional[User]):
    if user is None:
        return None

    if user.token is not None:
        return BearerAuth(user.token)

    if user.exec:
        return ExecAuth(user.exec)

    if user.username and user.password:
        return httpx.BasicAuth(user.username, user.password)

    if user.auth_provider:
        raise ConfigError("auth-provider not supported")


def user_cert(user: User, abs_file):
    """Extract user certificates"""
    if user.client_cert or user.client_cert_data:
        return (
            FileStr(user.client_cert_data) or abs_file(user.client_cert),
            FileStr(user.client_key_data) or abs_file(user.client_key),
        )
    return None


def verify_cluster(cluster: Cluster, user: User, abs_file, trust_env: bool = True):
    """setup certificate verification"""
    if cluster.certificate_auth:
        ctx = ssl.create_default_context(cafile=abs_file(cluster.certificate_auth))
    elif cluster.certificate_auth_data:
        ctx = ssl.create_default_context(cafile=FileStr(cluster.certificate_auth_data))
    else:
        ctx = httpx.create_ssl_context(verify=not cluster.insecure, trust_env=trust_env)
    cert = user_cert(user, abs_file)
    if cert:
        ctx.load_cert_chain(*cert)
    return ctx
