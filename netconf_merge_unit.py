#!/usr/bin/env python3

import unittest
import difflib

from xmlmerge import merge_tree, MergeError
from lxml import etree

# TODO:
#  - Verify that operation and key are removed from output...
#    e.g. copy a subtree
#  - Test for different type of elements: text only vs. contains subelements.



class MergeXMLTestCase(unittest.TestCase):
    def merge_xml(self, l, r):
        parser = etree.XMLParser(remove_blank_text=True)
        ltree = etree.fromstring(l, parser)
        rtree = etree.fromstring(r, parser)
        xml = merge_tree(ltree, rtree)
        return etree.tostring(ltree, pretty_print=True).decode('utf-8')





class MergeTestCase(MergeXMLTestCase):

   def test_nothing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
</config>
"""
        o = """\
<config>
</config>
"""
        xml = self.merge_xml(r, l)
        self.assertEqual(xml, o)

   def test_not_existing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
  <b>Bee</b>
</config>
"""
        o = """\
<config>
<a><name>Kilroy</name></a><b>Bee</b></config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_existing_single(self):
        l = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <a>
    <age>42</age>
  </a>
  <b>Bee</b>
</config>
"""
        o = """\
<config>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <b>Bee</b>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_existing_multiple(self):
        l = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
  <b>Ahh</b>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <a>
    <age>42</age>
  </a>
  <b>Bee</b>
</config>
"""
        o = """\
<config>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <b>Bee</b>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_text(self):
        l = """\
<config>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <b key="*">Bee</b>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)
        self.assertEqual(e.exception.args, ('Attribute key can not be used '
                                            'with text only elements.',))

   def test_key_non_existing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
<a><name>Kilroy</name><age>42</age></a></config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_non_existing2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_existing(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_existing2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_wildcard(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="*">
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)




class ReplaceTestCase(MergeXMLTestCase):

   def test_text_empty(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <b  operation="replace">Ahh</b>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)

   def test_text_exist(self):
        l = """\
<config>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <b  operation="replace">Bee</b>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)
        self.assertEqual(e.exception.args, ('Operation replace can not be used '
                                            'with text only elements.',))

   def test_text_key(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <b  operation="replace" key="*">Bee</b>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)
        self.assertEqual(e.exception.args, ('Attribute key can not be used '
                                            'with text only elements.',))

   def test_key_non_existing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <a operation="replace" key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
<a><name>Kilroy</name><age>42</age></a></config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_non_existing2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
    <length>5'4"</length>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="replace" key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
    <length>5'4"</length>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_existing(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
    <weight>140</weight>
  </a>
  <a>
    <name>Kilroy</name>
    <length>6'2"</length>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="replace" key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
    <weight>140</weight>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_existing2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <length>6'2"</length>
  </a>
  <a>
    <name>Kilroy</name>
    <weight>190</weight>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="replace" key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_wildcard(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="replace" key="*">
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <age>42</age>
  </a>
  <a>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)



class AddTestCase(MergeXMLTestCase):

   def test_text_empty(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <b  operation="add">Ahh</b>
  <b  operation="add">Ahh</b>
  <b  operation="add">Bee</b>
</config>
"""
        o = """\
<config>
<b>Ahh</b><b>Ahh</b><b>Bee</b></config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_text_exist(self):
        l = """\
<config>
  <b>Ahh</b>
  <b>Bee</b>
</config>
"""
        r = """\
<config>
  <b  operation="add">Ahh</b>
  <b  operation="add">Bee</b>
  <b  operation="add">Cee</b>
</config>
"""
        o = """\
<config>
  <b>Ahh</b>
  <b>Bee</b>
  <b>Ahh</b>
  <b>Bee</b>
  <b>Cee</b>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_text_key(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <b  operation="add" key="*">Bee</b>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)
        self.assertEqual(e.exception.args, ('Attribute key can not be used '
                                            'with operation add.',))

   def test_key(self):
        l = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="add" key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)
        self.assertEqual(e.exception.args, ('Attribute key can not be used '
                                            'with operation add',))



class DeleteTestCase(MergeXMLTestCase):

   def test_text_empty(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <b  operation="delete">Ahh</b>
  <b  operation="delete">Bee</b>
</config>
"""
        o = """\
<config>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_text_exist(self):
        l = """\
<config>
  <b>Ahh</b>
  <b>Bee</b>
</config>
"""
        r = """\
<config>
  <b  operation="delete">Bee</b>
  <b  operation="delete">Cee</b>
</config>
"""
        o = """\
<config>
  <b>Ahh</b>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_text_all(self):
        l = """\
<config>
  <b>Ahh</b>
  <b>Bee</b>
</config>
"""
        r = """\
<config>
  <b  operation="delete"/>
</config>
"""
        o = """\
<config/>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_text_key(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <b  operation="delete" key="*">Bee</b>
</config>
"""
        with self.assertRaises(MergeError) as e:
            xml = self.merge_xml(l, r)
        # TODO: This exception should be changed. It indicates that it can
        #       be used for other elements.
        self.assertEqual(e.exception.args, ('Attribute key can not be used '
                                            'with text only elements.',))

   def test_key(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="delete" key="name">
    <name>Kilroy</name>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="delete" key="name">
    <name>Kilroy</name>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_wildcard(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a operation="delete" key="*">
    <name>Kilroy</name>
  </a>
</config>
"""
        o = """\
<config/>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)







if __name__ == '__main__':
    unittest.main()
