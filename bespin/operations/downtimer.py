from bespin.errors import UnknownDowntimerSystem, FailedAlertingSystem, FailedAlertingSystems, ProgrammerError

from six.moves.urllib.parse import urlencode
from getpass import getpass
import requests
import logging
import json

log = logging.getLogger("bespin.operations.downtimer")

class Downtimer(object):
    def __init__(self, downtime_options, dry_run=False):
        self.systems = {}
        self.dry_run = dry_run
        self.downtime_options = downtime_options

    def register_system(self, name, options):
        if not hasattr(options, "type"):
            raise ProgrammerError("Programmer passed in an object that doesn't have the required type attribute... silly programmer")

        if options.type != "nagios":
            raise BadConfiguration("Sorry, only support nagios alerting system for now")

        self.systems[options.name] = NagiosDowntimer(options.endpoint, verify_ssl=options.verify_ssl, dry_run=self.dry_run)

    def get_system(self, name):
        if name in self.systems:
            return self.systems[name]
        else:
            raise UnknownDowntimerSystem(name=name)

    def downtime(self, *args):
        """For all the systems in our options, do a downtime"""
        self.execute_systems("downtime", *args)

    def undowntime(self, *args):
        """For all the systems in our options, do an undowntime"""
        self.execute_systems("undowntime", *args)

    def execute_systems(self, method, duration, author, comment):
        """Execute some method on all the known alerting systems"""
        errors = []
        for system, options in self.downtime_options.items():
            try:
                retrieved = self.get_system(system)
            except UnknownDowntimerSystem as error:
                errors.append(error)
                continue

            creds = retrieved.determine_creds(author)

            try:
                getattr(retrieved, method)(creds, options, duration, comment)
            except FailedAlertingSystem as error:
                errors.append(error)

        if errors:
            raise FailedAlertingSystems("Failed to {0}".format(method), _errors=errors)

class NagiosDowntimer(object):
    """Downtimer that knows about nagios"""
    def __init__(self, endpoint, verify_ssl=True, dry_run=False):
        self.dry_run = dry_run
        self.endpoint = endpoint
        self.verify_ssl = verify_ssl

    def action(self, method, creds, options, duration, comment):
        for host in options.hosts:
            if ',' in host:
                host, service = host.split(",")
            else:
                service = None

            data = dict(host=host, duration=duration, author=creds["username"], comment=comment)
            desc = host
            if service:
                desc = "{0}({1})".format(desc, service)
                data["service"] = service

            if self.dry_run:
                log.info("DRYRUN: would %s %s", method, desc)
            else:
                if method == "downtime":
                    url = "{0}/schedule_downtime".format(self.endpoint)
                else:
                    url = "{0}/cancel_downtime".format(self.endpoint)

                log.debug("Posting %s to %s", data, url)
                headers = {"Content-Type": "application/json"}
                res = requests.post(url, json.dumps(data).encode('utf-8'), verify=self.verify_ssl, auth=(creds['username'], creds.get('password', '')), headers=headers)
                succeeded = False
                if res.status_code == 200:
                    try:
                        content = json.loads(res.content.decode('utf-8'))
                        if content.get("success") == True:
                            succeeded = True
                    except (ValueError, TypeError) as error:
                        log.error("Failed to parse json from nagios\tgot=%s\terror=%s", res.content, error)

                if succeeded:
                    log.info("%s: %s: ok", method, desc)
                else:
                    log.error("%s :%s: FAILED %s", method, desc, res.content)
                    raise FailedAlertingSystem("nagios", error=res.content, desc=desc)

    def downtime(self, *args):
        self.action("downtime", *args)

    def undowntime(self, *args):
        self.action("undowntime", *args)

    def determine_creds(self, username):
        """Determine if we're already authenticated, if not get some password"""
        log.info("Seeing if already authenticated with endpoint\tendpoint=%s", self.endpoint)
        res = requests.get(self.endpoint, verify=self.verify_ssl)
        if res.status_code == 401:
            password = getpass("Please enter your ldap password for {0}: ".format(username))
            return {"username": username, "password": password}
        else:
            return {"username": username}

