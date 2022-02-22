#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

from copy import deepcopy
import json
import sys
from  lxml import etree as ET

"""
Operations:
 - merge (default)
 - create
 - replace
 - delete
 - remove

TODO:
 - Start with schema from root...
"""

# TODO:
# - Refactor code: Look over structure and simplify if possible.
# - Add rules to control where to create e.g. before, after, ...
# - Preserve empty lines and adjust fix indentation...
# - Handle xmlns prefix on operation
# - Check key presence on lnode 

class MergeError(Exception):
    pass

def fix_indentation(lnode, rnode):
    # add indentation (note! any garbage text will be copied as well!)
    # remove one newline to not add one extra empty line
    # does not work for all indentations...
#    list(lnode)[-1:][0].tail += rnode.text.replace('\n', '', 1)
    pass

def has_subelements(e):
    return len(e)>0

def no_subelements(e):
    return len(e)==0

def cleanup_attributes(node):
    for c in node:
        if 'operation' in c.attrib:
            del c.attrib['operation']
        #TBD
        if 'key' in c.attrib:
            del c.attrib['key']
        if has_subelements(c):
            cleanup_attributes(c)

def no_ns(tag):
    if '}' in tag:
        tag = tag.rsplit('}', 1)[1]
    return tag

def name_in_keyleafs(k, kl):
    for ns, l in kl:
        if k == l: return True
    return False

def find_no_ns(c, tag):
    for e in c:
        if tag == no_ns(e.tag):
            return e

def find_all_no_ns(c, tag):
    elems = []
    for e in c:
        if tag == no_ns(e.tag):
            elems.append(e)
    return elems

def merge_tree(lnode, rnode, schema):
    for c in rnode:
        rtag = no_ns(c.tag)
        rtype, *rrest = schema[rtag]
        # Schema validation
        if rtag not in schema.keys():
            raise MergeError(f"ERROR: Tag {rtag} not found in schema.")

        operation = 'merge' # default
        if 'operation' in c.attrib:
            operation = c.attrib.get('operation')
            del c.attrib['operation']
        elif '{urn:ietf:params:xml:ns:netconf:base:1.0}operation' in c.attrib:
            operation = c.attrib.get('{urn:ietf:params:xml:ns:netconf:base:1.0}operation')
            del c.attrib['{urn:ietf:params:xml:ns:netconf:base:1.0}operation']

        keyname = key = None 
        if rtype == 'list': 
            # TODO: Support for multiple leafs in key
            keyname = rrest[1][0][1]
            if keyname:
                # TODO: Handle namespaces...
                for z in c:
                    if keyname == no_ns(z.tag):
                        key = z.text.strip()
                if not key:
                    raise MergeError(f'List key leaf "{keyname}" not found.')

        ## TODO: Use schema
        #if 'key' in c.attrib:
        #    keyname = c.attrib.get('key')
        #    if keyname:
        #        v = c.find(keyname)
        #        if v is not None:
        #            key = v.text.strip()
        #    del c.attrib['key'], v
        #    if no_subelements(c):
        #        if operation == 'create':
        #            raise MergeError('Attribute key can not be used with '
        #                             'operation create.')
        #        else:
        #            raise MergeError('Attribute key can not be used with '
        #                             'text only elements.')

        if keyname is not None:
            assert rtype == 'list'
            t,tc,kl = schema[rtag]
            if not name_in_keyleafs(keyname, kl):
                print(f"ERROR: Key leaf {keyname} not in schema.")
                sys.exit(1)
            


        lcs = lnode.findall(c.tag)

        if operation == 'create':
            if not lcs:
                lnode.append(c)
            else:
                for zc in lcs:
                    for zl in zc:
                        if keyname == no_ns(zl.tag):
                            if key == zl.text.strip():
                                raise MergeError(f'Element {no_ns(zc.tag)} '
                                                 f'with {keyname}={key} '
                                                 f'already exists.')
                lc = lcs.pop() # Last element
                lnode.insert(lnode.index(lc)+1, c)

        elif not lcs: # ========= No elements in ltress ==========

            if operation == 'merge':
                fix_indentation(lnode, rnode)
                lnode.append(deepcopy(c))
            elif operation == 'replace':
                if no_subelements(c):
                    raise MergeError('Operation replace can not be used '
                                     'with text only elements.')
                fix_indentation(lnode, rnode)
                lnode.append(deepcopy(c))
            elif operation == 'merge':
                fix_indentation(lnode, rnode)
                lnode.append(deepcopy(c))
            else: # delete
                pass

        else:          # ========== one or more elements ==========

            if operation == 'merge':
                if no_subelements(c):
                    pos = lnode.index(lcs[0])
                    for lc in lcs:
                        lnode.remove(lc)
                    lnode.insert(pos, deepcopy(c))
                    del pos
                else:
                    if keyname is not None:
                        found = False
                        for lc in lcs:
                            ltag = no_ns(lc.tag)
                            # Schema validation
                            if ltag not in schema.keys():
                                print(f"ERROR: Tag {ltag} not found in schema:")
                                sys.exit(1)
                            k = find_no_ns(lc, keyname)
                            if k is not None and k.text.strip() == key:
                                found = True
                                cschema = schema[ltag]
                                merge_tree(lc, deepcopy(c), cschema[1])
                        if not found:
                            lnode.insert(lnode.index(lc)+1, deepcopy(c))
                            del found
                    else:
                        for lc in lcs:
                            ltag = no_ns(lc.tag)
                            # Schema validation
                            if ltag not in schema.keys():
                                print(f"ERROR: Tag {ltag} not found in schema:")
                                sys.exit(1)
                            cschema = schema[ltag]
                            merge_tree(lc, deepcopy(c), cschema[1])

            elif operation == 'replace':
                if no_subelements(c):
                    raise MergeError('Operation replace can not be used '
                                     'with text only elements.')
                else:
                    if keyname is not None:
                        found = False
                        for lc in lcs:
                            ltag = no_ns(lc.tag)
                            # Schema validation
                            if ltag not in schema.keys():
                                print(f"ERROR: Tag {ltag} not found in schema:")
                                sys.exit(1)
                            k = find_no_ns(lc, keyname)
                            if k is not None and k.text.strip() == key:
                                found = True
                                lnode.replace(lc, deepcopy(c))
                        if not found:
                            lnode.insert(lnode.index(lc)+1, deepcopy(c))
                            del found
                    else:
                        for lc in lcs:
                            x4merge_tree(lc, deepcopy(c), schema)

            elif operation in ['delete', 'remove']:
                if no_subelements(c):
                    for lc in lcs:
                        if c.text is None or c.text.strip() == lc.text.strip():
                            lnode.remove(lc)
                else:
                    #if keyname is None:
                    #    raise MergeError('No key specified for operation delete.')
                    deleted = False
                    for lc in lcs:
                        k = find_no_ns(lc, keyname)
                        if k is not None and k.text.strip() == key:
                            lnode.remove(lc)
                            deleted = True
                    if operation == 'delete' and not deleted:
                            raise MergeError(f'Element {no_ns(lc.tag)} '
                                             f'with {keyname}={key} '
                                             f'does not exists.')
                    del deleted
    

def main(files, schema, unit_test=False):
    ltree = None
    try:
        parser = ET.XMLParser(remove_blank_text=True) if unit_test else None
        for filename in files:
            doc = ET.parse(filename, parser)
            if ltree is None:
                ltree = doc
            else:
                # Verify that the root tags are the same
                assert(ltree.getroot().tag == doc.getroot().tag)
                # Merge the trees
                merge_tree(ltree.getroot(), doc.getroot(), schema)

        if ltree is not None:
            cleanup_attributes(ltree.getroot())
            return 0, ET.tostring(ltree, pretty_print=unit_test).decode('utf-8')
    except MergeError as e:
        return 1, f"ERROR: {e}"


if __name__ == "__main__":
    schema_file = json.loads(open(sys.argv[1]).read())
    tree = schema_file['tree']
    rootkey = list(tree.keys())[0]
    schema = tree[rootkey][1]
    status, xml = main(sys.argv[2:], schema, True)
    print(xml)
    sys.exit(status)
