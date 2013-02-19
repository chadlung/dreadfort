import json
import falcon

from meniscus.api import ApiResource, load_body, abort
from meniscus.model.util import find_tenant, find_host, find_host_profile
from meniscus.model.tenant import Tenant, Host, HostProfile, EventProducer


def _tenant_not_found():
    abort(falcon.HTTP_404, 'Unable to locate tenant.')


def _tenant_already_exists():
    abort(falcon.HTTP_400, 'Tenant already exists.')


def _host_not_found():
    abort(falcon.HTTP_400, 'Unable to locate host.')


def _profile_not_found():
    abort(falcon.HTTP_400, 'Unable to locate host profile.')


def format_tenant(tenant):
    if not isinstance(tenant, dict):
        tenant = tenant.__dict__

    return {'id': tenant['id'],
            'tenant_id': tenant['tenant_id']}


def format_event_producer(event_producer):
    if not isinstance(event_producer, dict):
        event_producer = event_producer.__dict__
    
    return {'name': event_producer['name'],
            'pattern': event_producer['pattern']}


def format_event_producers(event_producers):
    formatted_event_producers = []

    for event_producer in event_producers:
        formatted_event_producers.append(format_event_producer(event_producer))

    return formatted_event_producers


def format_host_profile(profile):
    event_producers = []

    if not isinstance(profile, dict):
        profile = profile.__dict__

    for event_producer in profile['event_producers']:
        event_producers.append(format_event_producer(event_producer))

    return {'id': profile['id'],
            'name': profile['name'],
            'event_producers': event_producers}


def format_host_profiles(profiles):
    formatted_profiles = []

    for profile in profiles:
        formatted_profiles.append(format_host_profile(profile))
        
    return formatted_profiles


def format_host(host):
    if not isinstance(host, dict):
        host = host.__dict__

    if 'profile' in host:
        host_profile = format_host_profile(host['profile'])
    else:
        host_profile = dict()
    
    return {'id': host['id'],
            'hostname': host['hostname'],
            'ip_address': host['ip_address'],
            'profile': host_profile}


def format_hosts(hosts):
    formatted_hosts = []

    for host in hosts:
        formatted_hosts.append(format_host(host))
        
    return formatted_hosts


class VersionResource(ApiResource):

    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200
        resp.body = json.dumps({'v1': 'current'})


class TenantResource(ApiResource):

    def __init__(self, db_session):
        self.db = db_session

    def on_post(self, req, resp):
        body = load_body(req)
        tenant_id = body['tenant_id']

        tenant = find_tenant(self.db, tenant_id=tenant_id)

        if tenant:
            abort(falcon.HTTP_400, 'Tenant with tenant_id {0} '
                  'already exists'.format(tenant_id))

        new_tenant = Tenant(tenant_id)
        self.db.add(new_tenant)
        self.db.commit()
        
        resp.status = falcon.HTTP_201
        resp.set_header('Location', '/v1/tenant/{0}'.format(tenant_id))


class UserResource(ApiResource):

    def __init__(self, db_session):
        self.db = db_session

    def on_get(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(format_tenant(tenant))

    def on_delete(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        self.db.delete(tenant)
        self.db.commit()

        resp.status = falcon.HTTP_200


class HostProfilesResource(ApiResource):
    
    def __init__(self, db_session):
        self.db = db_session

    def on_get(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(format_host_profiles(tenant.profiles))

    def on_post(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        body = load_body(req)
        profile_name = body['name']

        # Check if the tenant already has a profile with this name
        for profile in tenant.profiles:
            if profile.name == profile_name:
                abort(falcon.HTTP_400, 'Profile with name {0} already exists.'
                      .format(profile.name, profile.id))

        # Create the new profile for the host
        new_host_profile = HostProfile(tenant.id, profile_name)
        tenant.profiles.append(new_host_profile)
        
        self.db.add(new_host_profile)
        self.db.commit()

        resp.status = falcon.HTTP_201
        resp.set_header('Location',
                        '/v1/{0}/profiles/{1}'
                        .format(tenant_id, new_host_profile.id))


class HostProfileResource(ApiResource):
    
    def __init__(self, db_session):
        self.db = db_session

    def on_get(self, req, resp, tenant_id, profile_id):
        profile = find_host_profile(self.db, id=profile_id,
                                    when_not_found=_profile_not_found)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(format_host_profile(profile))

    def on_delete(self, req, resp, tenant_id, profile_id):
        profile = find_host_profile(self.db, id=profile_id,
                                    when_not_found=_profile_not_found)

        self.db.delete(profile)
        self.db.commit()

        resp.status = falcon.HTTP_200


class EventProducersResource(ApiResource):
    def __init__(self, db_session):
        self.db = db_session

    def on_get(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(format_event_producers(tenant.event_producers))

    def on_post(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        body = load_body(req)
        event_producer_name = body['name']
        event_producer_pattern = body['pattern']

        #if durable or encrypted aren't specified, set to False
        if 'durable' in body.keys():
            event_producer_durable = body['durable']
        else:
            event_producer_durable = False

        if 'encrypted' in body.keys():
            event_producer_encrypted = body['encrypted']
        else:
            event_producer_encrypted = False

        # Check if the event_producer already has a profile with this name
        for event_producer in tenant.event_producers:
            if event_producer.name == event_producer_name:
                abort(falcon.HTTP_400,
                      'Producer {0} with name {1} already exists.'
                      .format(event_producer.id, event_producer.name))

        # Create the new profile for the host
        new_event_producer = EventProducer(tenant.id, event_producer_name,
                                           event_producer_pattern,
                                           event_producer_durable,
                                           event_producer_encrypted)

        tenant.event_producers.append(new_event_producer)

        self.db.add(new_event_producer)
        self.db.commit()

        resp.status = falcon.HTTP_201
        resp.set_header('Location',
                        '/v1/{0}/producers/{1}'
                        .format(tenant_id, new_event_producer.id))


class EventProducerResource(ApiResource):

    def __init__(self, db_session):
        self.db = db_session

    def on_put(self, req, resp, tenant_id, profile_id):
        profile = find_host_profile(self.db, id=profile_id,
                                    when_not_found=_profile_not_found)

        body = load_body(req)
        hostname = body['name']
        ip_address = body['pattern']


class HostsResource(ApiResource):
    
    def __init__(self, db_session):
        self.db = db_session

    def on_get(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(format_hosts(tenant.hosts))

    def on_post(self, req, resp, tenant_id):
        tenant = find_tenant(self.db, tenant_id=tenant_id,
                             when_not_found=_tenant_not_found)

        body = load_body(req)
        hostname = body['hostname']
        ip_address = body['ip_address']

        #if profile id is not in post message, then use a null profile
        if 'profile_id' in body.keys():
            profile_id = body['profile_id']
        else:
            profile_id = None
            profile = None

        #if profile id is in post message, then make sure it is valid profile
        if profile_id:
            profile = find_host_profile(self.db, id=profile_id,
                                        when_not_found=_profile_not_found)

        # Check if the tenant already has a host with this hostname
        for host in tenant.hosts:
            if host.hostname == hostname:
                abort(falcon.HTTP_400, 'Host with hostname {0} already exists with'
                      ' id={1}'.format(hostname, host.id))

        # Create the new host definition
        new_host = Host(hostname, ip_address, profile)
        
        self.db.add(new_host)
        tenant.hosts.append(new_host)
        self.db().commit()

        resp.status = falcon.HTTP_201
        resp.set_header('Location',
                        '/v1/{0}/hosts/{1}'
                        .format(tenant_id, new_host.id))


class HostResource(ApiResource):
    
    def __init__(self, db_session):
        self.db = db_session

    def on_get(self, req, resp, tenant_id, host_id):
        host = find_host(self.db, host_id,
                         when_not_found=_host_not_found)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(format_host(host))

    def on_put(self, req, resp, tenant_id, host_id):
        host = find_host(self.db, host_id,
                         when_not_found=_host_not_found)

        body = load_body(req)
        profile_id = body['profile_id']

        profile = find_host_profile(self.db, id=profile_id,
                                    when_not_found=_profile_not_found)
        host.profile = profile
        self.db.commit()

        resp.status = falcon.HTTP_200

    def on_delete(self, req, resp, tenant_id, host_id):
        host = find_host(self.db, host_id,
                         when_not_found=_host_not_found)

        self.db.delete(host)
        self.db().commit()
        resp.status = falcon.HTTP_200
