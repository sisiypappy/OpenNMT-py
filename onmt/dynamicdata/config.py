import collections
import itertools
import os
import yaml

import jsonschema

#def validate_schema(data_config):
#    # FIXME: use package resources
#    schema_path = 'data_config.schema.yaml'
#    with open(schema_path, 'r') as fobj:
#        schema = yaml.safe_load(fobj)
#    jsonschema.validate(data, schema)

def _inverse_groups(data_config):
    for input in data_config['inputs']:
        group = data_config['inputs'][input]['group']
        if '_inputs' not in data_config['groups'][group]:
            data_config['groups'][group]['_inputs'] = []
        data_config['groups'][group]['_inputs'].append(input)
    for group in data_config['groups']:
        if '_inputs' in data_config['groups'][group]:
            data_config['groups'][group]['_inputs'].sort()

def _share_inputs(data_config):
    for group in data_config['groups']:
        if 'share_inputs' in data_config['groups'][group]:
            share_from = data_config['groups'][group]['share_inputs']
            inputs = data_config['groups'][share_from]['_inputs']
            data_config['groups'][group]['_inputs'] = inputs

def _remove_shared_inputs(shard_config):
    to_remove = []
    for group in shard_config['groups']:
        if 'share_inputs' in shard_config['groups'][group]:
            to_remove.append(group)
    for group in to_remove:
        del shard_config['groups'][group]

def _normalize_sizes(data_config):
    size_per_group = collections.Counter()
    corpora_per_group = collections.Counter()
    for input in data_config['inputs']:
        group = data_config['inputs'][input]['group']
        if 'size' not in data_config['inputs'][input]:
            continue
        size = data_config['inputs'][input]['size']
        size_per_group[group] += size
        corpora_per_group[group] += 1
    for input in data_config['inputs']:
        group = data_config['inputs'][input]['group']
        if 'size' not in data_config['inputs'][input]:
            if corpora_per_group[group] == 0:
                # no sizes set
                data_config['inputs'][input]['size'] = 1
            else:
                # 
                data_config['inputs'][input]['size'] = int(
                    100 / corpora_per_group[group])
        else:
            size = data_config['inputs'][input]['size']
            data_config['inputs'][input]['size'] = int(
                100 * size / size_per_group[group])

def _all_transforms(data_config):
    all_transforms = set()
    for group in data_config['groups']:
        all_transforms.update(data_config['groups'][group].get('transforms', []))
    data_config['_transforms'] = list(sorted(all_transforms))

def _group_defaults(data_config):
    for group in data_config['groups']:
        if 'split' not in data_config['groups'][group]:
            data_config['groups'][group]['split'] = 'train'
        if 'weight' not in data_config['groups'][group]:
            data_config['groups'][group]['weight'] = 1

def read_data_config(data_config_file):
    with open(data_config_file, 'r') as fobj:
        data_config = yaml.safe_load(fobj)
    _inverse_groups(data_config)
    _normalize_sizes(data_config)
    _all_transforms(data_config)
    _group_defaults(data_config)
    #validate_schema(data_config)
    return data_config

def _filter_config(config, sub_config, path, rules):
    decision = 'continue'
    current = path[-1]
    for rule in rules:
        rule_path, rule_decision = rule
        if all(b is None or a == b for (a, b) in itertools.zip_longest(path, rule_path)):
            decision = rule_decision
            break
    if decision == 'keep':
        sub_config[current] = config[current]
    elif decision == 'drop':
        return
    else:
        if isinstance(config[current], dict):
            sub_config[current] = {}
            for key in config[current]:
                extended_path = path + [key]
                _filter_config(
                    config[current], sub_config[current], extended_path, rules)
        else:
            # default keep
            sub_config[current] = config[current]

def sharding_only(data_config):
    """ retains only config used in sharding step """
    rules = ((('meta', 'shard'), 'keep'),
             (('meta', 'train'), 'drop'),
             (('groups', None, 'transforms'), 'drop'),
             (('groups', None, 'weight'), 'drop'),
             (('groups', None, 'meta'), 'drop'),
             (('inputs',), 'keep'),
             (('_transforms',), 'drop'),
            )
    sub_config = {}
    for key in data_config:
        _filter_config(data_config, sub_config, [key], rules)
    _remove_shared_inputs(sub_config)
    return sub_config

def save_shard_config(data_config):
    stored_shard_config_file = os.path.join(
        data_config['meta']['shard']['rootdir'],
        'stored_shard_config.yaml')
    if os.path.exists(stored_shard_config_file):
        raise Exception('stored shard config "{}"'
            ' already exists, not overwriting'.format(stored_shard_config_file))
    os.makedirs(
        data_config['meta']['shard']['rootdir'],
        exist_ok=True)
    with open(stored_shard_config_file, 'w') as fobj:
        yaml.safe_dump(data_config, fobj)

def dict_diff(a, b):
    keys = list(sorted(set(a.keys()).union(b.keys())))
    a_pruned = {}
    b_pruned = {}
    for key in keys:
        if a.get(key, None) == b.get(key, None):
            # equal can be pruned
            continue
        if key in a and key in b and isinstance(a[key], dict) and isinstance(b[key], dict):
            a_sub, b_sub = dict_diff(a[key],  b[key])
            a_pruned[key] = a_sub
            b_pruned[key] = b_sub
        else:
            a_pruned[key] = a.get(key, '**** MISSING ****')
            b_pruned[key] = b.get(key, '**** MISSING ****')
    return a_pruned, b_pruned


def verify_shard_config(data_config):
    stored_shard_config_file = os.path.join(
        data_config['meta']['shard']['rootdir'],
        'stored_shard_config.yaml')
    shard_config = sharding_only(data_config)
    with open(stored_shard_config_file, 'r') as fobj:
        stored_shard_config = yaml.safe_load(fobj)
    for group in stored_shard_config['groups']:
        if '_inputs' in stored_shard_config['groups'][group]:
            stored_shard_config['groups'][group]['_inputs'].sort()
    if not shard_config == stored_shard_config:
        old, new = dict_diff(stored_shard_config, shard_config)
        raise Exception(
            'data_config not compatible with stored shard config.\n'
            'old {}\nnew {}\n'.format(old, new))
