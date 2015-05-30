from bespin.formatter import MergedOptionStringFormatter
from bespin.errors import BadNetScaler

from input_algorithms.spec_base import Spec, dictof, listof, string_spec, container_spec, match_spec, overridden, formatted, set_options, any_spec, optional_spec
from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
import requests
import logging
import json
import six
import re

log = logging.getLogger("bespin.option_spec.netscaler")

netscaler_binding_spec = lambda: container_spec(NetscalerBinding, match_spec(((list, ) + six.string_types, listof(string_spec())), (dict, set_options(tagged=listof(string_spec())))))

class valid_environment_spec(Spec):
    def normalise_filled(self, meta, val):
        if "environments" not in meta.everything:
            raise BespinError("Please specify {environments}")

        val = string_spec().normalise(meta, val)
        available = list(meta.everything["environments"].keys())
        if val not in available:
            raise BespinError("Please choose a valid environment", meta=meta, wanted=val, available=available)

        return val

class netscaler_config_spec(Spec):
    def normalise_filled(self, meta, val):
        typ = formatted(overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter).normalise(meta, val)
        name = formatted(overridden("{_key_name_0}"), formatter=MergedOptionStringFormatter).normalise(meta, val)
        special = {}
        kls = special.get(typ, GenericNetscalerConfig)

        formatted_string = formatted(string_spec(), formatter=MergedOptionStringFormatter)
        formatted_options = dictof(string_spec(), match_spec((six.string_types, formatted_string), fallback=any_spec()))

        options = dict(
              typ=overridden(typ)
            , name=overridden(name)
            , bindings=dictof(string_spec()
            , netscaler_binding_spec())
            , tags=listof(string_spec())
            , options=formatted_options
            , overrides=formatted_options
            , binding_options=formatted_options
            , environments=optional_spec(listof(valid_environment_spec()))
            )

        if typ == "sslcertkey":
            options["link"] = listof(string_spec())
        as_dict = set_options(**options).normalise(meta, val)
        return kls(**dict((name, as_dict[name]) for name in options))

configuration_spec = lambda: dictof(string_spec(), dictof(string_spec(), netscaler_config_spec()))

class GenericNetscalerConfig(dictobj):
    fields = ["typ", "name", "bindings", "tags", "options", "binding_options", "environments", "overrides", ("link", NotSpecified)]

    def dependencies(self, configuration):
        """Get the bindings dependencies for this configuration item"""
        for typ, binding_options in self.bindings.items():
            if typ in configuration:
                for item in binding_options.wanted(configuration[typ].values()):
                    if item in configuration[typ]:
                        yield configuration[typ][item].long_name

    def payload(self, environment, current=None):
        """Create payload for creating/updating the config"""
        if hasattr(self.options, "as_dict"):
            options = self.options.as_dict()
        else:
            options = dict(self.options)

        if environment in self.overrides:
            overrides = self.overrides[environment]
            if hasattr(overrides, "as_dict"):
                overrides = overrides.as_dict()
            else:
                overrides = dict(overrides)
            options.update(overrides)

        if current:
            changes = {}
            for key, val in options.items():
                if current.get(key) != val:
                    changes[key] = (current.get(key), val)

            if changes:
                log.info("changes=%s", changes)
                ret = {self.typ: options}
            else:
                return
        else:
            log.info("new=%s", options)
            ret = {self.typ: options}

        return ret

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
        , "dry_run": "Whether this is a dry run or not"

        , "username": "The username"
        , "password": "The password"

        , "configuration_username": "The username for configuration syncing"
        , "configuration_password": "The password for configuration syncing"

        , "verify_ssl": "Whether to verify ssl connections"
        , "configuration": "Configuration to put into the netscaler"
        , "syncable_environments": "List of environments that may be synced"
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
        return False

    def url(self, part):
        return "{0}/nitro/{1}/config/{2}".format(self.host, self.nitro_api_version, part)

    @property
    def headers(self):
        headers = {"Cookie": "sessionid="}
        if self.sessionid:
            headers["Cookie"] = "sessionid={0}".format(self.sessionid)
            headers["Set-Cookie"] = "NITRO_AUTH_TOKEN={0}".format(self.sessionid)
        return headers

    def content_type(self, typ):
        return "application/vnd.com.citrix.netscaler.{0}+json".format(typ)

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
        return self.post("server?action=enable", {"server": {"name": server}}, content_type=self.content_type("server"))

    def disable_server(self, server):
        """Disable a particular server in the netscaler"""
        log.info("Disabling %s in netscaler", server)
        return self.post("server?action=disable", {"server": {"name": server}}, content_type=self.content_type("server"))

    def bind_policy(self, policy, vserver, priority):
        """Bind a policy to a vserver"""
        log.info("Binding %s to %s with weight %s", policy, vserver, priority)
        return self.put("/lbvserver_responderpolicy_binding/{0}".format(vserver), {"lbvserver_responderpolicy_binding": {"policyName": policy, "name": vserver, "priority": priority}, "params": {"action": "bind"}}, content_type=self.content_type("lbvserver_responderpolicy_binding"))

    def unbind_policy(self, policy, vserver):
        """unbind a policy to a service group"""
        log.info("Unbinding %s from %s", policy, vserver)
        return self.delete("/lbvserver_responderpolicy_binding/{0}?args=policyname:{1}".format(vserver, policy), content_type=self.content_type("lbvserver_responderpolicy_binding"))

    def is_bound(self, typ_one, thing_one, typ_two, thing_two):
        """Determine if something is bound to something else"""
        try:
            bound = self._is_bound(typ_one, thing_one, typ_two, thing_two)
        except BadNetScaler as error:
            # sigh, some combinations aren't done both ways
            if error.kwargs["errorcode"] in (1088, 1232):
                bound = False
            else:
                raise

        if not bound:
            try:
                # Some combinations aren't the same both ways
                bound = self._is_bound(typ_two, thing_two, typ_one, thing_one)
            except BadNetScaler as error:
                if error.kwargs["errorcode"] in (1088, 1232):
                    bound = False
                else:
                    raise

        return bound

    def _is_bound(self, binding_to_typ, binding_to, bound_typ, bound):
        """Determine if something is bound to something else"""
        typ, _, name_str = self.combined_typ(binding_to_typ, bound_typ)
        found = self.get("/{0}/{1}".format(typ, binding_to), content_type=self.content_type(typ))
        if found["errorcode"] != 0:
            raise BadNetScaler("Failed to get", binding_to=binding_to, bound=bound, msg=found.get("msg"), error_code=found["errorcode"], typ=typ)

        if typ not in found:
            log.debug("typ not in found\tfound=%s\ttyp=%s", found, typ)
            return False
        else:
            if name_str == "monitorName":
                name_str = "monitor_name"
            elif name_str == "serviceGroupName":
                name_str = "servicegroupname"
            log.debug("Looking for %s in first\tfirst=%s\twant=%s", name_str, found[typ], bound)
            return any(f.get(name_str) == bound or f.get(name_str.lower()) == bound for f in found[typ])

    def post(self, url, payload, content_type=None):
        return self.interact("post", url, payload, content_type=content_type)

    def put(self, url, payload, content_type=None):
        return self.interact("put", url, payload, content_type=content_type)

    def get(self, url, content_type=None):
        return self.interact("get", url, content_type=content_type)

    def delete(self, url, content_type=None):
        return self.interact("delete", url, content_type=content_type)

    def get_current(self, config):
        """Get back (exists, current) for this config"""
        try:
            url = "/{0}/{1}".format(config.typ, config.name)
            content_type = self.content_type(config.typ)
            current = self.get(url, content_type=content_type)
            return True, current
        except BadNetScaler as error:
            msg = error.kwargs.get("msg", "")
            if msg.startswith("No such resource") or re.match("^No such [^ ]+ exists", msg):
                pass
            elif config.typ == "systemcmdpolicy" and msg.startswith("Invalid argument"):
                pass
            elif config.typ == "sslcertkey" and msg.startswith("Certificate does not exist"):
                pass
            else:
                raise
        return False, None

    def sync(self, configuration, environment, config):
        log.info("Syncing %s", str(config))

        url = "/{0}/{1}".format(config.typ, config.name)
        content_type = self.content_type(config.typ)
        exists, current = self.get_current(config)

        if current is None:
            log.info("Resource doesn't exist, creating new one")
            self.post(url, config.payload(environment), content_type=content_type)
        else:
            current = current[config.typ][0]
            payload = config.payload(environment, dict(current))
            log.debug("Updating\tcurrent=%s", current)
            if not payload:
                log.debug("No changes required")
            else:
                self.put(url, payload, content_type=content_type)

        for typ, bindings in config.bindings.items():
            self.add_bindings(configuration, config, typ, bindings)

        if config.typ == "sslcertkey" and config.link is not NotSpecified:
            self.link_certs(config)

    def add_bindings(self, configuration, bind_to, typ, bindings):
        """Add bindings to bind_to of type 'typ'"""
        wanted = list(bindings.wanted(configuration[typ].values()))
        if not self.get_current(bind_to)[0]:
            log.info("Would bind <%s>(%s) to %s", typ, ', '.join(wanted), bind_to.long_name)
            return

        for thing in wanted:
            bound = self.is_bound(typ, thing, bind_to.typ, bind_to.name)

            if not bound:
                log.info("Binding <%s>(%s) to %s", typ, thing, bind_to.long_name)
                combined_typ, binding_name_str, name_str = self.combined_typ(bind_to.typ, typ)
                payload = {binding_name_str: bind_to.name, name_str: thing}
                payload.update(configuration[typ][thing].binding_options)
                self.post(combined_typ, {combined_typ: payload, "params": {"action": "bind"}}, content_type=self.content_type(combined_typ))
            else:
                log.debug("<%s(%s) already bound to %s", typ, thing, bind_to.long_name)

    def combined_typ(self, typ_one, typ_two):
        """Return (combined_typ, one_name_str, two_name_str) for these two types"""
        combined_typ = "{0}_{1}_binding".format(typ_one, typ_two)

        names = {"one": "name", "two": "name"}
        for num, val in (("one", typ_one), ("two", typ_two)):
            if val.endswith("policy"):
                names[num] = "policyName"
            elif val.endswith("service"):
                names[num] = "serviceName"
            elif val.endswith("monitor"):
                names[num] = "monitorName"
            elif val.endswith("servicegroup"):
                names[num] = "serviceGroupName"
            elif val.endswith("certkey"):
                names[num] = "certkey"
            elif val.endswith("user"):
                names[num] = "userName"

        if typ_one == "lbvserver" and typ_two == "sslcertkey":
            combined_typ = "sslvserver_sslcertkey_binding"
            names["one"] = "vservername"
            names["two"] = "certkeyname"

        return combined_typ, names["one"], names["two"]

    def link_certs(self, sslcertkey):
        """Link the certs defined for this certkey"""
        for link in sslcertkey.link:
            if not self.is_linked(sslcertkey.name, link):
                log.info("Link %s to %s", link, sslcertkey.name)
                self.link_cert(sslcertkey.name, link)

    def is_linked(self, link_into, being_linked):
        """Is <being_linked> linked to <link_into>?"""
        try:
            ret = self.get("sslcertkey/{0}".format(link_into))
        except BadNetScaler as error:
            msg = error.kwargs.get("msg", "")
            if msg.startswith("Invalid argument"):
                return False
            else:
                raise

        if 'sslcertkey' not in ret:
            return False

        if 'linkcertkeyname' not in ret['sslcertkey'][0]:
            return False

        return ret['sslcertkey'][0]['linkcertkeyname'] == being_linked

    def link_cert(self, link_into, being_linked):
        """Link <being_linked> to <link_into>"""
        self.post("sslcertlink/{0}".format(link_into), {"params": {"action": "link"}, "sslcertlink": {"certkeyname": being_linked}}, content_type=self.content_type("sslcertlink"))

    def interact(self, method, url, payload=None, content_type=None):
        """interact with the netscaler"""
        try:
            data = None
            if payload:
                data = {"object": json.dumps(payload)}

            headers = dict(self.headers)
            if content_type:
                headers["Content-Type"] = content_type
                data = json.dumps(payload)

            log.debug("%s %s -- %s", method, url, headers)
            if self.dry_run and method != "get" and url not in ('/login', '/logout'):
                log.info("DRYRUN: %s %s", method, self.url(url))
                return {"errorcode": 0}

            res = getattr(requests, method)(self.url(url), data=data, headers=headers, verify=self.verify_ssl)
        except requests.exceptions.HTTPError as error:
            raise BadNetScaler("Failed to talk to the netscaler", error=error, status_code=getattr(error, "status_code", ""))

        try:
            content = res.content.decode('utf-8')
            if content:
                content = json.loads(content)
            else:
                content = {"errorcode": 0}
        except (ValueError, TypeError) as error:
            raise BadNetScaler("Failed to parse netscaler response", error=error)

        if content["errorcode"] != 0:
            raise BadNetScaler("Netscaler says no", msg=content["message"], errorcode=content["errorcode"])

        return content

