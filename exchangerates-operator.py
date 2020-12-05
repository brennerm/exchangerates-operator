#!/usr/bin/env python3

import kopf
import kubernetes.config as k8s_config
import kubernetes.client as k8s_client
import requests


exchange_rate_crd = k8s_client.V1CustomResourceDefinition(
    api_version="apiextensions.k8s.io/v1",
    kind="CustomResourceDefinition",
    metadata=k8s_client.V1ObjectMeta(name="exchangerates.operators.brennerm.github.io"),
    spec=k8s_client.V1CustomResourceDefinitionSpec(
        group="operators.brennerm.github.io",
        versions=[k8s_client.V1CustomResourceDefinitionVersion(
            name="v1",
            served=True,
            storage=True,
            schema=k8s_client.V1CustomResourceValidation(
                open_apiv3_schema=k8s_client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "spec": k8s_client.V1JSONSchemaProps(
                            type="object",
                            properties={"currency":  k8s_client.V1JSONSchemaProps(
                                type="string",
                                enum=["CAD","CHF","GBP","JPY","PLN","USD"]
                            )}
                        ),
                        "status": k8s_client.V1JSONSchemaProps(
                            type="object",
                            x_kubernetes_preserve_unknown_fields=True
                        )
                    }
                )
            )
        )],
        scope="Namespaced",
        names=k8s_client.V1CustomResourceDefinitionNames(
            plural="exchangerates",
            singular="exchangerate",
            kind="ExchangeRate",
            short_names=["er"]
        )
    )
)

try:
    k8s_config.load_kube_config()
except k8s_config.ConfigException:
    k8s_config.load_incluster_config()

api_instance = k8s_client.ApiextensionsV1Api()
try:
    api_instance.create_custom_resource_definition(exchange_rate_crd)
except k8s_client.rest.ApiException as e:
    if e.status == 409:
        print("CRD already exists")
    else:
        raise e

def get_exchange_rate(currency):
    exchange_rates_url = 'https://api.exchangeratesapi.io/latest?symbols='
    return requests.get(f"{exchange_rates_url}{currency}").json()['rates'][currency]

def create_exchange_rate_config_map(namespace, data):
    api_instance = k8s_client.CoreV1Api()
    return api_instance.create_namespaced_config_map(namespace, data)


def update_exchange_rate_config_map(namespace, name, new_data):
    api_instance = k8s_client.CoreV1Api()
    return api_instance.patch_namespaced_config_map(name, namespace, new_data)

@kopf.on.create('operators.brennerm.github.io', 'v1', 'exchangerates')
def on_create(namespace, spec, body, **kwargs):
    currency = spec['currency']
    rate = get_exchange_rate(currency)
    data = __rate_to_config_map_data(rate)

    kopf.adopt(data)

    configmap = create_exchange_rate_config_map(namespace, data)
    return {'configmap-name': configmap.metadata.name}


@kopf.on.update('operators.brennerm.github.io', 'v1', 'exchangerates')
def on_update(namespace, name, spec, status, **kwargs):
    currency = spec['currency']
    rate = get_exchange_rate(currency)
    name = status['on_create']['configmap-name']
    data = __rate_to_config_map_data(rate)

    update_exchange_rate_config_map(namespace, name, data)

def __rate_to_config_map_data(rate):
    return {
        'data': {
            'rate': str(rate)
        }
    }