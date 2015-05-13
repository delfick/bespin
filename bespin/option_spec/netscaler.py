from bespin.formatter import MergedOptionStringFormatter
from bespin.errors import BadConfiguration, BadNetScaler

from input_algorithms.spec_base import Spec, dictof, listof, string_spec, container_spec, match_spec, overridden, formatted, set_options, dictionary_spec
from input_algorithms.validators import Validator
from input_algorithms.dictobj import dictobj
import requests
import logging
import json
import six

log = logging.getLogger("bespin.option_spec.netscaler")

netscaler_binding_spec = lambda: container_spec(NetscalerBinding, match_spec(((list, ) + six.string_types, listof(string_spec())), (dict, set_options(tagged=listof(string_spec())))))

class netscaler_config_spec(Spec):
    def normalise_filled(self, meta, val):
        typ = formatted(overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter).normalise(meta, val)
        name = formatted(overridden("{_key_name_0}"), formatter=MergedOptionStringFormatter).normalise(meta, val)
        special = {}
        kls = special.get(typ, GenericNetscalerConfig)
        as_dict = set_options(typ=overridden(typ), name=overridden(name), bindings=dictof(string_spec(), netscaler_binding_spec()), tags=listof(string_spec()), options=dictionary_spec()).normalise(meta, val)
        return kls(**dict((name, as_dict[name]) for name in ("typ", "name", "bindings", "tags", "options")))

configuration_spec = lambda: dictof(string_spec(), dictof(string_spec(), netscaler_config_spec()))

class GenericNetscalerConfig(dictobj):
    fields = {"typ", "name", "bindings", "tags", "options"}

    def dependencies(self, configuration):
        """Get the bindings dependencies for this configuration item"""
        for typ, binding_options in self.bindings.items():
            if typ in configuration:
                for item in binding_options.wanted(configuration[typ].values()):
                    if item in configuration[typ]:
                        yield configuration[typ][item].long_name

    def __str__(self):
        return "{0} -- {1}".format(" ".join(self.typ.split("_")), self.name)
    __unicode__ = __str__

    @property
    def long_name(self):
        return "<{0}>({1})".format(self.typ, self.name)

    def __lt__(self, other):
        return self.name < other.name

    def __hash__(self):
        return hash(self.typ + self.name)

class NetscalerBinding(dictobj):
    fields = ["bindings"]

    def wanted(self, available):
        if isinstance(self.bindings, list):
            for item in self.bindings:
                yield item
        else:
            for item in available:
                if any(t in item.tags for t in self.bindings["tagged"]):
                    yield item.name

class NetScaler(dictobj):
    fields = {
          "host": "The address of the netscaler"

        , "username": "The username"
        , "password": "The password"

        , "configuration_username": "The username for configuration syncing"
        , "configuration_password": "The password for configuration syncing"

        , "verify_ssl": "Whether to verify ssl connections"
        , "configuration": "Configuration to put into the netscaler"
        , ("nitro_api_version", "v1"): "Defaults to v1"
        }

    @property
    def sessionid(self):
        return getattr(self, "_sessionid", "")

    @sessionid.setter
    def sessionid(self, val):
        self._sessionid = val

    def __enter__(self):
        self.login(configuration=getattr(self, "syncing_configuration", False))
        return self

    def __exit__(self, *args, **kwargs):
        self.logout()

    def url(self, part):
        return "{0}/nitro/{1}/config/{2}".format(self.host, self.nitro_api_version, part)

    @property
    def headers(self):
        headers = {"Cookie": "sessionid=", "ContentType": "application/x-www-form-urlencoded"}
        if self.sessionid:
            headers["Cookie"] = "sessionid={0}".format(self.sessionid)
            headers["Set-Cookie"] = "NITRO_AUTH_TOKEN={0}".format(self.sessionid)
        return headers

    def login(self, configuration=False):
        """Log into the netscaler and set self.sessionid"""
        if configuration:
            username = self.configuration_username
            password = self.configuration_password
        else:
            username = self.username
            password = self.password

        while callable(password):
            password = password()
        log.info("Logging into the netscaler at %s", self.host)
        res = self.post("/login", {"login": {"username": username, "password": password}})
        self.sessionid = res["sessionid"]

    def logout(self):
        """Log out of the netscaler and reset self.sessionid"""
        try:
            log.info("Logging out of the netscaler")
            self.post("/logout", {"logout": {}})
        except BadNetScaler as error:
            log.error("Failed to logout of the netscaler: %s", error)
        self.sessionid = ""

    def enable_server(self, server):
        """Enable a particular server in the netscaler"""
        log.info("Enabling %s in netscaler", server)
        return self.post("/server", {"server": {"name": server}, "params": {"action": "enable"}})

    def disable_server(self, server):
        """Disable a particular server in the netscaler"""
        log.info("Disabling %s in netscaler", server)
        return self.post("/server", {"server": {"name": server}, "params": {"action": "disable"}})

    def bind_policy(self, policy, vserver, weight):
        """Bind a policy to a vserver"""
        log.info("Binding %s to %s with weight %s", policy, vserver, weight)
        return self.put("/lbvserver_service_binding", {"lbvserver_service_binding": {"servicename": policy, "name": vserver, "weight": weight}, "params": {"action": "bind"}})

    def block_policy(self, policy, vserver):
        """Block a policy to a service group"""
        return self.put("/lbvserver_service_binding", {"lbvserver_service_binding": {"servicename": policy, "name": vserver}, "params": {"action": "block"}})

    def policies(self, vserver):
        """Return information about policies attached to the vserver"""
        return self.get("/lbvserver_service_binding/{0}".format(vserver))

    def post(self, url, payload):
        return self.interact("post", url, payload)

    def put(self, url, payload):
        return self.interact("post", url, payload)

    def put(self, url):
        return self.interact("get", url)

    def sync(self, config, dry_run=False):
        dry_run_str = ""
        if dry_run:
            dry_run_str = "DRYRUN: "
        log.info("%sSyncing %s", dry_run_str, str(config))
        if not dry_run:
            pass

    def interact(self, method, url, payload=None):
        """interact with the netscaler"""
        try:
            data = None
            if payload:
                data = {"object": json.dumps(payload)}
            res = getattr(requests, method)(self.url(url), data=data, headers=self.headers, verify=self.verify_ssl)
        except requests.exceptions.HTTPError as error:
            raise BadNetScaler("Failed to talk to the netscaler", error=error, status_code=getattr(error, "status_code", ""))

        try:
            content = json.loads(res.content.decode('utf-8'))
        except (ValueError, TypeError) as error:
            raise BadNetScaler("Failed to parse netscaler response", error=error)

        if content["errorcode"] != 0:
            raise BadNetScaler("Netscaler says no", msg=content["message"], errorcode=content["errorcode"])

        return content

