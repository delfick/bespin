from bespin.errors import BespinError
from bespin import helpers as hp

from radssh.console import RadSSHConsole
from radssh.authmgr import AuthManager
from radssh.plugins import jumpbox
from radssh import plugins, config
from radssh.ssh import Cluster

from six.moves import input
import binascii
import requests
import paramiko
import logging
import getpass
import socket
import uuid
import time
import json
import sys
import os

log = logging.getLogger("bespin.operations.ssh")

def insert_char_every_n_chars(string, char='\n', every=64):
    return char.join(string[i:i + every] for i in range(0, len(string), every))

def fingerprint(key):
    return insert_char_every_n_chars(binascii.hexlify(key.get_fingerprint()).decode('utf-8'), ':', 2)

class SSH(object):
    def __init__(self, ips, command, ssh_user, ssh_key=None, proxy=None, proxy_ssh_key=None, proxy_ssh_user=None, acceptable_return_codes=None):
        self.ips = ips
        self.proxy = proxy
        self.command = command
        self.ssh_key = ssh_key
        self.ssh_user = ssh_user
        self.proxy_ssh_key = proxy_ssh_key
        self.proxy_ssh_user = proxy_ssh_user
        self.acceptable_return_codes = acceptable_return_codes
        if self.acceptable_return_codes is None:
            self.acceptable_return_codes = [0]

    def run(self):
        jb = None
        defaults = config.load_default_settings()
        defaults['hostkey.verify'] = 'ignore'

        original_paramiko_agent = paramiko.Agent
        with hp.a_temp_file() as fle:
            if self.proxy and self.proxy_ssh_key:
                fle.write("keyfile|{0}|{1}\n".format(self.proxy, self.proxy_ssh_key).encode('utf-8'))
            if self.ssh_key:
                fle.write("keyfile|*|{0}\n".format(self.ssh_key).encode('utf-8'))
            fle.close()

            auth_file = fle.name if (self.ssh_key or self.proxy_ssh_key) else None

            if self.proxy:
                jb = plugins.load_plugin(jumpbox.__file__)
                jb.init(auth=AuthManager(self.proxy_ssh_user, auth_file=auth_file), defaults=defaults)

            login = AuthManager(self.ssh_user, auth_file=auth_file, include_agent=True)
            keys = {}
            for key in login.agent_connection.get_keys():
                ident = str(uuid.uuid1())
                identity = type("Identity", (object, ), {
                      "__str__": lambda s: ident
                    , "get_name": lambda s: key.get_name()
                    , "asbytes": lambda s: key.asbytes()
                    , "sign_ssh_data": lambda s, *args, **kwargs: key.sign_ssh_data(*args, **kwargs)
                    })()
                keys[identity] = key
                login.deferred_keys[identity] = key

        try:
            console = RadSSHConsole()
            connections = [(ip, None) for ip in self.ips]
            if jb:
                jb.add_jumpbox(self.proxy)
                connections = list((ip, socket) for _, ip, socket in jb.do_jumpbox_connections(self.proxy, self.ips))

            cluster = None
            try:
                log.info("Connecting")
                authenticated = False
                for _ in hp.until(timeout=120):
                    if authenticated:
                        break

                    cluster = Cluster(connections, login, console=console, defaults=defaults)
                    for _ in hp.until(timeout=10, step=0.5):
                        if not any(cluster.pending):
                            break

                    if cluster.pending:
                        raise BespinError("Timedout waiting to connect to some hosts", waiting_for=cluster.pending.keys())

                    for _ in hp.until(timeout=10, step=0.5):
                        connections = list(cluster.connections.values())
                        if any(isinstance(connection, socket.gaierror) for connection in connections):
                            raise BespinError("Some connections failed!", failures=[conn for conn in connections if isinstance(conn, socket.gaierror)])

                        if all(conn.authenticated for conn in connections):
                            break

                    authenticated = all(conn.authenticated for conn in cluster.connections.values())
                    if not authenticated:
                        unauthenticated = [host for host, conn in cluster.connections.items() if not conn.authenticated]
                        log.info("Failed to authenticate will try to reconnect in 5 seconds\tunauthenticate=%s", unauthenticated)
                        time.sleep(5)

                # Try to reauth if not authenticated yet
                unauthenticated = [host for host, conn in cluster.connections.items() if not conn.authenticated]
                if unauthenticated:
                    for host in unauthenticated:
                        print('{0:14s} : {1}'.format(str(host), cluster.connections[host]))
                    raise BespinError("Timedout waiting to authenticate all the hosts, do you have an ssh-agent running?", unauthenticated=unauthenticated)

                failed = []
                for host, status in cluster.connections.items():
                    print('{0:14s} : {1}'.format(str(host), status))
                    if type(status) is socket.gaierror:
                        failed.append(host)

                if failed:
                    raise BespinError("Failed to connect to some hosts", failed=failed)

                cluster.run_command(self.command)

                error = False
                for host, job in cluster.last_result.items():
                    if not job.completed or job.result.return_code not in self.acceptable_return_codes:
                        log.error('%s -%s', host, cluster.connections[host])
                        log.error('%s, %s', job, job.result.status)
                        error = True

                if error:
                    raise BespinError("Failed to run the commands")
            finally:
                if cluster:
                    cluster.close_connections()
        finally:
            paramiko.Agent = original_paramiko_agent

class RatticSSHKeys(object):
    def __init__(self, host, bastion_location, bastion_path, instance_location, instance_path):
        self.host = host
        self.bastion_path = bastion_path
        self.instance_path = instance_path
        self.bastion_location = bastion_location
        self.instance_location = instance_location

    def retrieve(self, typ):
        if typ == "bastion":
            return self.retrieve_key(self.host, self.bastion_location, self.bastion_path)
        else:
            return self.retrieve_key(self.host, self.instance_location, self.instance_path)

    def retrieve_key(self, host, location, path):
        if os.path.exists(path):
            try:
                current_key = paramiko.RSAKey.from_private_key(open(path))
                if fingerprint(current_key) != self.rattic_fingerprint(host, location):
                    log.info("You current key is not the correct fingerprint, downloading new key\tlooking_at=%s", path)
                else:
                    return False
            except paramiko.ssh_exception.SSHException as error:
                log.error("You current key is invalid (%s), downloading it now\tlooking_at=%s", error, path)
        else:
            log.info("No key found, downloading it now\tlooking_at=%s", path)

        self.rattic_download_key(host, location, path)
        return True

    def rattic_fingerprint(self, host, location):
        return requests.get("{0}/cred/detail/{1}/fingerprint".format(host, location)).content.decode('utf-8')

    @property
    def rattic_api_key(self):
        if getattr(self, "_rattic_api_key", None) is None:
            self._rattic_api_key = self.make_api_key()
        return self._rattic_api_key

    def make_api_key(self):
        api_key_url = "{0}/account/generate_api_key".format(self.host)
        cookies = requests.get(api_key_url, headers={"Referer": self.host}).cookies
        data = {'rattic_tfa_generate_api_key-current_step': 'auth', 'csrfmiddlewaretoken': cookies['csrftoken']}

        sys.stderr.write("username: ")
        sys.stderr.flush()
        username = input()

        sys.stderr.write("password: ")
        sys.stderr.flush()
        password = getpass.getpass("")

        data['auth-username'] = username
        data['auth-password'] = password

        res = requests.post(api_key_url, data=data, cookies=cookies, headers={"Referer": self.host})
        if res.status_code not in (200, 400):
            print(res.content.decode('utf-8'))
            raise BespinError("Failed to generate an api token from rattic")

        if res.status_code == 400:
            data['rattic_tfa_generate_api_key-current_step'] = 'token'
            sys.stderr.write("token: ")
            sys.stderr.flush()
            token = input()
            data['token-otp_token'] = token
            res = requests.post(api_key_url, data=data, cookies=cookies, headers={"Referer": self.host})

        return "ApiKey {0}:{1}".format(username, res.content.decode('utf-8'))

    def rattic_download_key(self, host, location, path):
        cred_url = "{0}/api/v1/cred/{1}/".format(host, location)
        headers = {"Authorization": self.rattic_api_key, "Referer": self.host}
        res = requests.get(cred_url, headers=headers)

        if os.path.exists(path):
            os.remove(path)

        parent_dir = os.path.dirname(path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        with open(path, 'w') as fle:
            fle.write(json.loads(res.content.decode('utf-8'))['ssh_key'])

