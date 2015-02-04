from bespin.errors import BespinError
from bespin import helpers as hp

from radssh.console import RadSSHConsole
from radssh.authmgr import AuthManager
from radssh.plugins import jumpbox
from radssh import plugins, config
from radssh.ssh import Cluster

import logging

log = logging.getLogger("bespin.actions.ssh")

class SSH(object):
    def __init__(self, ips, command, ssh_user, ssh_key, proxy=None, proxy_ssh_key=None, proxy_ssh_user=None):
        self.ips = ips
        self.proxy = proxy
        self.command = command
        self.ssh_key = ssh_key
        self.ssh_user = ssh_user
        self.proxy_ssh_key = proxy_ssh_key
        self.proxy_ssh_user = proxy_ssh_user

    def run(self):
        jb = None
        defaults = config.load_default_settings()
        defaults['hostkey.verify'] = 'ignore'

        with hp.a_temp_file() as fle:
            if self.proxy:
                fle.write("keyfile|{0}|{1}\n".format(self.proxy, self.proxy_ssh_key).encode('utf-8'))
            fle.write("keyfile|*|{0}\n".format(self.ssh_key).encode('utf-8'))
            fle.close()

            if self.proxy:
                jb = plugins.load_plugin(jumpbox.__file__)
                jb.init(auth=AuthManager(self.proxy_ssh_user, auth_file=fle.name), defaults=defaults)

            login = AuthManager(self.ssh_user, auth_file=fle.name)

        console = RadSSHConsole()
        connections = [(ip, None) for ip in self.ips]
        if jb:
            jb.add_jumpbox(self.proxy)
            connections = list((ip, socket) for _, ip, socket in jb.do_jumpbox_connections(self.proxy, self.ips))

        cluster = None
        try:
            log.info("Connecting")
            cluster = Cluster(connections, login, console=console, defaults=defaults)
            for host, status in cluster.status():
                print('{0:14s} : {1}'.format(str(host), status))
            cluster.run_command(self.command)

            error = False
            for host, job in cluster.last_result.items():
                if not job.completed or job.result.return_code != 0:
                    print(host, cluster.connections[host])
                    print(job, job.result.status, job.result.stderr)

                    log.error('%s -%s', host, cluster.connections[host])
                    log.error('%s, %s, %s', job, job.result.status, job.result.stderr)
                    error = True

            if error:
                raise BespinError("Failed to run the commands")
        finally:
            if cluster:
                cluster.close_connections()

