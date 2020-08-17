from __future__ import print_function

import dns.resolver
import sys
import urllib3
import xml.etree.ElementTree as ET

try:
    from urlparse import urlparse
except:
    from urllib.parse import urlparse

BROADCAST_SCHEMES = ['fm', 'dab', 'drm', 'amss', 'hd']

SPI_NAMESPACE = 'http://www.worlddab.org/schemas/spi/31'
SPI_APP_LEGACY = 'radioepg'

SI_PATH = '/radiodns/spi/3.1/SI.xml'

http = urllib3.PoolManager()

def si(source, **kwargs):
    (urls, auth_fqdn) = resolve_urls(source)
    success = False
    for url in urls:
        try:
            parse_si(url, **dict(kwargs, resolved_auth_fqdn=auth_fqdn))
            success = True
            break
        except Exception as e:
            print(e, file=sys.stderr)
            continue
    if not success:
        print('All attempts to obtain SI file failed', file=sys.stderr)

def parse_si(url, **kwargs):
    resolved_auth_fqdn = kwargs.get('resolved_auth_fqdn')
    remove_non_authoritative_bearers = kwargs.get('remove_non_authoritative_bearers', False)

    response = http.request('GET', url)
    if response.status != 200:
        raise Exception('{url} returned a non-200 status ({status})'.format(url=url,
                                                                            status=response.status))

    root = ET.fromstring(response.data)
    ET.register_namespace('', SPI_NAMESPACE)

    if remove_non_authoritative_bearers:
        host = urlparse(url).netloc

        for service in root.iter('{{{namespace}}}service'.format(namespace=SPI_NAMESPACE)):
            for bearer in service.iter('{{{namespace}}}bearer'.format(namespace=SPI_NAMESPACE)):
                bearer_uri = bearer.attrib['id'].lower()
                if urlparse(bearer_uri).scheme not in BROADCAST_SCHEMES:
                    continue

                try:
                    auth_fqdn = resolve_bearer_uri(bearer_uri)
                except Exception:
                    # TODO: this should be more specific about what Exceptions are acceptable
                    name = get_service_name(service)
                    print('failed resolving {bearer} ({service}) in {url}'.format(bearer=bearer_uri,
                                                                                  service=name,
                                                                                  url=url),
                          file=sys.stderr)
                    service.remove(bearer)
                    continue

                if resolved_auth_fqdn:
                    if auth_fqdn != resolved_auth_fqdn:
                        name = get_service_name(service)
                        print('{actual} != {expected} for {bearer} ({service}) in {url}'.format(actual=auth_fqdn,
                                                                                                expected=resolved_auth_fqdn,
                                                                                                bearer=bearer_uri,
                                                                                                service=name, url=url),
                              file=sys.stderr)
                        service.remove(bearer)
                        continue

                else:
                    hosts = resolve_application(auth_fqdn, SPI_APP_LEGACY)
                    if host not in hosts:
                        name = get_service_name(service)
                        print('{actual} not in {expected} for {bearer} ({service}) in {url}'.format(actual=host,
                                                                                                    expected=hosts,
                                                                                                    bearer=bearer_uri,
                                                                                                    service=name,
                                                                                                    url=url),
                              file=sys.stderr)
                        service.remove(bearer)
                        continue

            # if len(service.findall('{{{namespace}}}bearer')) == 0:
            #     print 

    xml = ET.tostring(root, encoding='utf8', method='xml')

    output_filename = kwargs.get('output')
    if output_filename:
        try:
            file = open(output_filename, 'w')
            file.write(xml)
            file.close()
        except:
            print('failed writing to file {output_filename}'.format(filename=output_filename))
    else:
        print(xml)

def get_service_name(service):
    try:
        return service.find('{{{namespace}}}longName'.format(namespace=SPI_NAMESPACE)).text
    except:
        # TODO: this should be more specific about what Exceptions are acceptable
        pass
    try:
        return service.find('{{{namespace}}}mediumName'.format(namespace=SPI_NAMESPACE)).text
    except:
        # TODO: this should be more specific about what Exceptions are acceptable
        pass
    try:
        return service.find('{{{namespace}}}shortName'.format(namespace=SPI_NAMESPACE)).text
    except:
        # TODO: this should be more specific about what Exceptions are acceptable
        return 'No name'

def resolve_urls(source):
    params = urlparse(source)
    if params.scheme in BROADCAST_SCHEMES:
        # source appears to be a bearer URI, resolve it, then resolve SPI on against the auth fqdn
        auth_fqdn = resolve_bearer_uri(source)
        hosts = resolve_application(auth_fqdn, SPI_APP_LEGACY)
        targets = ['http://{host}{default_path}'.format(host=host,
                                                        default_path=SI_PATH) for host in hosts]
        return (targets, auth_fqdn)
    elif params.scheme in ['http', 'https']:
        # source appears to be an SI document URL
        if params.path == '':
            # it has no path, so add the default path and return
            targets = ['{scheme}://{host}{default_path}'.format(scheme=params.scheme,
                                                                host=params.netloc,
                                                                path=params.path,
                                                                default_path=SI_PATH)]
            return (targets, None)
        targets = ['{scheme}://{host}{path}'.format(scheme=params.scheme,
                                                    host=params.netloc,
                                                    path=params.path)]
        if params.path != SI_PATH:
            # source has an unusual path, so try the default path and a combination of the defined path and default
            targets.append('{scheme}://{host}{default_path}'.format(scheme=params.scheme,
                                                                    host=params.netloc,
                                                                    default_path=SI_PATH))
            targets.append('{scheme}://{host}{path}{default_path}'.format(scheme=params.scheme,
                                                                          host=params.netloc,
                                                                          path=params.path,
                                                                          default_path=SI_PATH))
        return (targets, None)
    else:
        try:
            hosts = resolve_application(source, SPI_APP_LEGACY)
            auth_fqdn = source
        except:
            # TODO: this should be more specific about what Exceptions are acceptable
            hosts = [source]
            auth_fqdn = None
        targets = ['http://{host}{default_path}'.format(host=host,
                                                        default_path=SI_PATH) for host in hosts]        
        return (targets, auth_fqdn)

def resolve_bearer_uri(uri):
    params = urlparse(uri)
    if params.scheme not in BROADCAST_SCHEMES:
        raise Exception('Not a valid bearer')
    fqdn = '{params}.{scheme}.radiodns.org.'.format(params='.'.join(params.path.split('.')[::-1]),
        scheme=params.scheme)
    answers = dns.resolver.query(fqdn, 'CNAME')
    for rdata in answers:
        return rdata

def resolve_application(auth_fqdn, application, **kwargs):
    srv = '_{application}._{transport_protocol}.{auth_fqdn}'.format(application=application,
                                                                    transport_protocol=kwargs.get('transport_protocol', 'tcp'),
                                                                    auth_fqdn=auth_fqdn)
    results = []
    for rdata in dns.resolver.query(srv, 'SRV'):
        port = ':{port}'.format(port=rdata.port) if rdata.port != 80 else ''
        results.append({
            'host': '{target}{port}'.format(target=str(rdata.target)[:-1], port=port),
            'priority': rdata.priority,
            'weight': rdata.weight
        })
    sorted_results = sorted(results, key=lambda result: (result['priority'], -result['weight']))
    return [result['host'] for result in sorted_results]
