#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
r""" A JSON data encoder and decoder.

 This Python module implements the JSON (http://json.org/) data
 encoding format; a subset of ECMAScript (aka JavaScript) for encoding
 primitive data types (numbers, strings, booleans, lists, and
 associative arrays) in a language-neutral simple text-based syntax.
 
 It can encode or decode between JSON formatted strings and native
 Python data types.  Normally you would use the encode() and decode()
 functions defined by this module, but if you want more control over
 the processing you can use the JSON class.

 This implementation tries to be as completely cormforming to all
 intricacies of the standards as possible.  It can operate in strict
 mode (which only allows JSON-compliant syntax) or a non-strict mode
 (which allows much more of the whole ECMAScript permitted syntax).
 This includes complete support for Unicode strings (including
 surrogate-pairs for non-BMP characters), and all number formats
 including negative zero and IEEE 754 non-numbers such a NaN or
 Infinity.

 The JSON/ECMAScript to Python type mappings are:
    ---JSON---             ---Python---
    null                   None
    undefined              undefined  (note 1)
    Boolean (true,false)   bool  (True or False)
    Integer                int or long  (note 2)
    Float                  float
    String                 str or unicode  ( "..." or u"..." )
    Array [a, ...]         list  ( [...] )
    Object {a:b, ...}      dict  ( {...} )
    
    -- Note 1. an 'undefined' object is declared in this module which
       represents the native Python value for this type when in
       non-strict mode.

    -- Note 2. some ECMAScript integers may be up-converted to Python
       floats, such as 1e+40.  Also integer -0 is converted to
       float -0, so as to preserve the sign (which ECMAScript requires).

 In addition, when operating in non-strict mode, several IEEE 754
 non-numbers are also handled, and are mapped to specific Python
 objects declared in this module:

     NaN (not a number)     nan    (float('nan'))
     Infinity, +Infinity    inf    (float('inf'))
     -Infinity              neginf (float('-inf'))

 When encoding Python objects into JSON, you may use types other than
 native lists or dictionaries, as long as they support the minimal
 interfaces required of all sequences or mappings.  This means you can
 use generators and iterators, tuples, UserDict subclasses, etc.

 To make it easier to produce JSON encoded representations of user
 defined classes, if the object has a method named json_equivalent(),
 then it will call that method and attempt to encode the object
 returned from it instead.  It will do this recursively as needed and
 before any attempt to encode the object using it's default
 strategies.  Note that any json_equivalent() method should return
 "equivalent" Python objects to be encoded, not an already-encoded
 JSON-formatted string.  There is no such aid provided to decode
 JSON back into user-defined classes as that would dramatically
 complicate the interface.
 
 When decoding strings with this module it may operate in either
 strict or non-strict mode.  The strict mode only allows syntax which
 is conforming to RFC 4627 (JSON), while the non-strict allows much
 more of the permissible ECMAScript syntax.

 The following are permitted when processing in NON-STRICT mode:

    * Unicode format control characters are allowed anywhere in the input.
    * All Unicode line terminator characters are recognized.
    * All Unicode white space characters are recognized.
    * The 'undefined' keyword is recognized.
    * Hexadecimal number literals are recognized (e.g., 0xA6, 0177).
    * String literals may use either single or double quote marks.
    * Strings may contain \x (hexadecimal) escape sequences, as well as the
      \v and \0 escape sequences.
    * Lists may have omitted (elided) elements, e.g., [,,,,,], with
      missing elements interpreted as 'undefined' values.
    * Object properties (dictionary keys) can be of any of the
      types: string literals, numbers, or identifiers (the later of
      which are treated as if they are string literals)---as permitted
      by ECMAScript.  JSON only permits strings literals as keys.

 Concerning non-strict and non-ECMAScript allowances:

    * Octal numbers: If you allow the 'octal_numbers' behavior (which
      is never enabled by default), then you can use octal integers
      and octal character escape sequences (per the ECMAScript
      standard Annex B.1.2).  This behavior is allowed, if enabled,
      because it was valid JavaScript at one time.

    * Multi-line string literals:  Strings which are more than one
      line long (contain embedded raw newline characters) are never
      permitted. This is neither valid JSON nor ECMAScript.  Some other
      JSON implementations may allow this, but this module considers
      that behavior to be a mistake.

 References:
    * JSON (JavaScript Object Notation)
      <http://json.org/>
    * RFC 4627. The application/json Media Type for JavaScript Object Notation (JSON)
      <http://www.ietf.org/rfc/rfc4627.txt>
    * ECMA-262 3rd edition (1999)
      <http://www.ecma-international.org/publications/files/ecma-st/ECMA-262.pdf>
    * IEEE 754-1985: Standard for Binary Floating-Point Arithmetic.
      <http://www.cs.berkeley.edu/~ejr/Projects/ieee754/>
    
"""

__author__ = "Deron Meranda <http://deron.meranda.us/>"
__date__ = "2008-12-17"
__version__ = "1.4"
__credits__ = """Copyright (c) 2006-2008 Deron E. Meranda <http://deron.meranda.us/>
Licensed under GNU LGPL 3.0 (GNU Lesser General Public License) or
later.  See LICENSE.txt included with this software.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
or <http://www.fsf.org/licensing/>.

"""

# ------------------------------
# useful global constants

content_type = 'application/json'
file_ext = 'json'
hexdigits = '0123456789ABCDEFabcdef'
octaldigits = '01234567'

# ----------------------------------------------------------------------
# Decimal and float types.
#
# If a JSON number can not be stored in a Python float without loosing
# precision and the Python has the decimal type, then we will try to
# use decimal instead of float.  To make this determination we need to
# know the limits of the float type, but Python doesn't have an easy
# way to tell what the largest floating-point number it supports.  So,
# we detemine the precision and scale of the float type by testing it.

try:
    # decimal module was introduced in Python 2.4
    import decimal
except ImportError:
    decimal = None

def determine_float_precision():
    """Returns a tuple (significant_digits, max_exponent) for the float type.
    """
    import math
    # Just count the digits in pi.  The last two decimal digits
    # may only be partial digits, so discount for them.
    whole, frac = repr(math.pi).split('.')
    sigdigits = len(whole) + len(frac) - 2

    # This is a simple binary search.  We find the largest exponent
    # that the float() type can handle without going infinite or
    # raising errors.
    maxexp = None
    minv = 0; maxv = 1000
    while True:
        if minv+1 == maxv:
            maxexp = minv - 1
            break
        elif maxv < minv:
            maxexp = None
            break
        m = (minv + maxv) // 2
        try:
            f = repr(float( '1e+%d' % m ))
        except ValueError:
            f = None
        else:
            if not f or f[0] < '0' or f[0] > '9':
                f = None
        if not f:
            # infinite
            maxv = m
        else:
            minv = m
    return sigdigits, maxexp

float_sigdigits, float_maxexp = determine_float_precision()

# ----------------------------------------------------------------------
# The undefined value.
#
# ECMAScript has an undefined value (similar to yet distinct from null).
# Neither Python or strict JSON have support undefined, but to allow
# JavaScript behavior we must simulate it.

class _undefined_class(object):
    """Represents the ECMAScript 'undefined' value."""
    __slots__ = []
    def __repr__(self):
        return self.__module__ + '.undefined'
    def __str__(self):
        return 'undefined'
    def __nonzero__(self):
        return False
undefined = _undefined_class()
del _undefined_class


# ----------------------------------------------------------------------
# Non-Numbers: NaN, Infinity, -Infinity
#
# ECMAScript has official support for non-number floats, although
# strict JSON does not.  Python doesn't either.  So to support the
# full JavaScript behavior we must try to add them into Python, which
# is unfortunately a bit of black magic.  If our python implementation
# happens to be built on top of IEEE 754 we can probably trick python
# into using real floats.  Otherwise we must simulate it with classes.

def _nonnumber_float_constants():
    """Try to return the Nan, Infinity, and -Infinity float values.
    
    This is unnecessarily complex because there is no standard
    platform- independent way to do this in Python as the language
    (opposed to some implementation of it) doesn't discuss
    non-numbers.  We try various strategies from the best to the
    worst.
    
    If this Python interpreter uses the IEEE 754 floating point
    standard then the returned values will probably be real instances
    of the 'float' type.  Otherwise a custom class object is returned
    which will attempt to simulate the correct behavior as much as
    possible.

    """
    try:
        # First, try (mostly portable) float constructor.  Works under
        # Linux x86 (gcc) and some Unices.
        nan = float('nan')
        inf = float('inf')
        neginf = float('-inf')
    except ValueError:
        try:
            # Try the AIX (PowerPC) float constructors
            nan = float('NaNQ')
            inf = float('INF')
            neginf = float('-INF')
        except ValueError:
            try:
                # Next, try binary unpacking.  Should work under
                # platforms using IEEE 754 floating point.
                import struct, sys
                xnan = '7ff8000000000000'.decode('hex')  # Quiet NaN
                xinf = '7ff0000000000000'.decode('hex')
                xcheck = 'bdc145651592979d'.decode('hex') # -3.14159e-11
                # Could use float.__getformat__, but it is a new python feature,
                # so we use sys.byteorder.
                if sys.byteorder == 'big':
                    nan = struct.unpack('d', xnan)[0]
                    inf = struct.unpack('d', xinf)[0]
                    check = struct.unpack('d', xcheck)[0]
                else:
                    nan = struct.unpack('d', xnan[::-1])[0]
                    inf = struct.unpack('d', xinf[::-1])[0]
                    check = struct.unpack('d', xcheck[::-1])[0]
                neginf = - inf
                if check != -3.14159e-11:
                    raise ValueError('Unpacking raw IEEE 754 floats does not work')
            except (ValueError, TypeError):
                # Punt, make some fake classes to simulate.  These are
                # not perfect though.  For instance nan * 1.0 == nan,
                # as expected, but 1.0 * nan == 0.0, which is wrong.
                class nan(float):
                    """An approximation of the NaN (not a number) floating point number."""
                    def __repr__(self): return 'nan'
                    def __str__(self): return 'nan'
                    def __add__(self,x): return self
                    def __radd__(self,x): return self
                    def __sub__(self,x): return self
                    def __rsub__(self,x): return self
                    def __mul__(self,x): return self
                    def __rmul__(self,x): return self
                    def __div__(self,x): return self
                    def __rdiv__(self,x): return self
                    def __divmod__(self,x): return (self,self)
                    def __rdivmod__(self,x): return (self,self)
                    def __mod__(self,x): return self
                    def __rmod__(self,x): return self
                    def __pow__(self,exp): return self
                    def __rpow__(self,exp): return self
                    def __neg__(self): return self
                    def __pos__(self): return self
                    def __abs__(self): return self
                    def __lt__(self,x): return False
                    def __le__(self,x): return False
                    def __eq__(self,x): return False
                    def __neq__(self,x): return True
                    def __ge__(self,x): return False
                    def __gt__(self,x): return False
                    def __complex__(self,*a): raise NotImplementedError('NaN can not be converted to a complex')
                if decimal:
                    nan = decimal.Decimal('NaN')
                else:
                    nan = nan()
                class inf(float):
                    """An approximation of the +Infinity floating point number."""
                    def __repr__(self): return 'inf'
                    def __str__(self): return 'inf'
                    def __add__(self,x): return self
                    def __radd__(self,x): return self
                    def __sub__(self,x): return self
                    def __rsub__(self,x): return self
                    def __mul__(self,x):
                        if x is neginf or x < 0:
                            return neginf
                        elif x == 0:
                            return nan
                        else:
                            return self
                    def __rmul__(self,x): return self.__mul__(x)
                    def __div__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float division')
                        elif x < 0:
                            return neginf
                        else:
                            return self
                    def __rdiv__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return 0.0
                    def __divmod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float divmod()')
                        elif x < 0:
                            return (nan,nan)
                        else:
                            return (self,self)
                    def __rdivmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return (nan, nan)
                        return (0.0, x)
                    def __mod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float modulo')
                        else:
                            return nan
                    def __rmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return x
                    def __pow__(self, exp):
                        if exp == 0:
                            return 1.0
                        else:
                            return self
                    def __rpow__(self, x):
                        if -1 < x < 1: return 0.0
                        elif x == 1.0: return 1.0
                        elif x is nan or x is neginf or x < 0:
                            return nan
                        else:
                            return self
                    def __neg__(self): return neginf
                    def __pos__(self): return self
                    def __abs__(self): return self
                    def __lt__(self,x): return False
                    def __le__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __eq__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __neq__(self,x):
                        if x is self:
                            return False
                        else:
                            return True
                    def __ge__(self,x): return True
                    def __gt__(self,x): return True
                    def __complex__(self,*a): raise NotImplementedError('Infinity can not be converted to a complex')
                if decimal:
                    inf = decimal.Decimal('Infinity')
                else:
                    inf = inf()
                class neginf(float):
                    """An approximation of the -Infinity floating point number."""
                    def __repr__(self): return '-inf'
                    def __str__(self): return '-inf'
                    def __add__(self,x): return self
                    def __radd__(self,x): return self
                    def __sub__(self,x): return self
                    def __rsub__(self,x): return self
                    def __mul__(self,x):
                        if x is self or x < 0:
                            return inf
                        elif x == 0:
                            return nan
                        else:
                            return self
                    def __rmul__(self,x): return self.__mul__(self)
                    def __div__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float division')
                        elif x < 0:
                            return inf
                        else:
                            return self
                    def __rdiv__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return -0.0
                    def __divmod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float divmod()')
                        elif x < 0:
                            return (nan,nan)
                        else:
                            return (self,self)
                    def __rdivmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return (nan, nan)
                        return (-0.0, x)
                    def __mod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float modulo')
                        else:
                            return nan
                    def __rmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return x
                    def __pow__(self,exp):
                        if exp == 0:
                            return 1.0
                        else:
                            return self
                    def __rpow__(self, x):
                        if x is nan or x is inf or x is inf:
                            return nan
                        return 0.0
                    def __neg__(self): return inf
                    def __pos__(self): return self
                    def __abs__(self): return inf
                    def __lt__(self,x): return True
                    def __le__(self,x): return True
                    def __eq__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __neq__(self,x):
                        if x is self:
                            return False
                        else:
                            return True
                    def __ge__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __gt__(self,x): return False
                    def __complex__(self,*a): raise NotImplementedError('-Infinity can not be converted to a complex')
                if decimal:
                    neginf = decimal.Decimal('-Infinity')
                else:
                    neginf = neginf(0)
    return nan, inf, neginf

nan, inf, neginf = _nonnumber_float_constants()
del _nonnumber_float_constants


# ----------------------------------------------------------------------
# String processing helpers

unsafe_string_chars = '"\\' + ''.join([chr(i) for i in range(0x20)])
def skipstringsafe( s, start=0, end=None ):
    i = start
    #if end is None:
    #    end = len(s)
    while i < end and s[i] not in unsafe_string_chars:
        #c = s[i]
        #if c in unsafe_string_chars:
        #    break
        i += 1
    return i
def skipstringsafe_slow( s, start=0, end=None ):
    i = start
    if end is None:
        end = len(s)
    while i < end:
        c = s[i]
        if c == '"' or c == '\\' or ord(c) <= 0x1f:
            break
        i += 1
    return i

def extend_list_with_sep( orig_seq, extension_seq, sepchar='' ):
    if not sepchar:
        orig_seq.extend( extension_seq )
    else:
        for i, x in enumerate(extension_seq):
            if i > 0:
                orig_seq.append( sepchar )
            orig_seq.append( x )

def extend_and_flatten_list_with_sep( orig_seq, extension_seq, separator='' ):
    for i, part in enumerate(extension_seq):
        if i > 0 and separator:
            orig_seq.append( separator )
        orig_seq.extend( part )


# ----------------------------------------------------------------------
# Unicode helpers
#
# JSON requires that all JSON implementations must support the UTF-32
# encoding (as well as UTF-8 and UTF-16).  But earlier versions of
# Python did not provide a UTF-32 codec.  So we must implement UTF-32
# ourselves in case we need it.

def utf32le_encode( obj, errors='strict' ):
    """Encodes a Unicode string into a UTF-32LE encoded byte string."""
    import struct
    try:
        import cStringIO as sio
    except ImportError:
        import StringIO as sio
    f = sio.StringIO()
    write = f.write
    pack = struct.pack
    for c in obj:
        n = ord(c)
        if 0xD800 <= n <= 0xDFFF: # surrogate codepoints are prohibited by UTF-32
            if errors == 'ignore':
                continue
            elif errors == 'replace':
                n = ord('?')
            else:
                cname = 'U+%04X'%n
                raise UnicodeError('UTF-32 can not encode surrogate characters',cname)
        write( pack('<L', n) )
    return f.getvalue()


def utf32be_encode( obj, errors='strict' ):
    """Encodes a Unicode string into a UTF-32BE encoded byte string."""
    import struct
    try:
        import cStringIO as sio
    except ImportError:
        import StringIO as sio
    f = sio.StringIO()
    write = f.write
    pack = struct.pack
    for c in obj:
        n = ord(c)
        if 0xD800 <= n <= 0xDFFF: # surrogate codepoints are prohibited by UTF-32
            if errors == 'ignore':
                continue
            elif errors == 'replace':
                n = ord('?')
            else:
                cname = 'U+%04X'%n
                raise UnicodeError('UTF-32 can not encode surrogate characters',cname)
        write( pack('>L', n) )
    return f.getvalue()


def utf32le_decode( obj, errors='strict' ):
    """Decodes a UTF-32LE byte string into a Unicode string."""
    if len(obj) % 4 != 0:
        raise UnicodeError('UTF-32 decode error, data length not a multiple of 4 bytes')
    import struct
    unpack = struct.unpack
    chars = []
    i = 0
    for i in range(0, len(obj), 4):
        seq = obj[i:i+4]
        n = unpack('<L',seq)[0]
        chars.append( unichr(n) )
    return u''.join( chars )


def utf32be_decode( obj, errors='strict' ):
    """Decodes a UTF-32BE byte string into a Unicode string."""
    if len(obj) % 4 != 0:
        raise UnicodeError('UTF-32 decode error, data length not a multiple of 4 bytes')
    import struct
    unpack = struct.unpack
    chars = []
    i = 0
    for i in range(0, len(obj), 4):
        seq = obj[i:i+4]
        n = unpack('>L',seq)[0]
        chars.append( unichr(n) )
    return u''.join( chars )


def auto_unicode_decode( s ):
    """Takes a string and tries to convert it to a Unicode string.

    This will return a Python unicode string type corresponding to the
    input string (either str or unicode).  The character encoding is
    guessed by looking for either a Unicode BOM prefix, or by the
    rules specified by RFC 4627.  When in doubt it is assumed the
    input is encoded in UTF-8 (the default for JSON).

    """
    if isinstance(s, unicode):
        return s
    if len(s) < 4:
        return s.decode('utf8')  # not enough bytes, assume default of utf-8
    # Look for BOM marker
    import codecs
    bom2 = s[:2]
    bom4 = s[:4]
    a, b, c, d = map(ord, s[:4])  # values of first four bytes
    if bom4 == codecs.BOM_UTF32_LE:
        encoding = 'utf-32le'
        s = s[4:]
    elif bom4 == codecs.BOM_UTF32_BE:
        encoding = 'utf-32be'
        s = s[4:]
    elif bom2 == codecs.BOM_UTF16_LE:
        encoding = 'utf-16le'
        s = s[2:]
    elif bom2 == codecs.BOM_UTF16_BE:
        encoding = 'utf-16be'
        s = s[2:]
    # No BOM, so autodetect encoding used by looking at first four bytes
    # according to RFC 4627 section 3.
    elif a==0 and b==0 and c==0 and d!=0: # UTF-32BE
        encoding = 'utf-32be'
    elif a==0 and b!=0 and c==0 and d!=0: # UTF-16BE
        encoding = 'utf-16be'
    elif a!=0 and b==0 and c==0 and d==0: # UTF-32LE
        encoding = 'utf-32le'
    elif a!=0 and b==0 and c!=0 and d==0: # UTF-16LE
        encoding = 'utf-16le'
    else: #if a!=0 and b!=0 and c!=0 and d!=0: # UTF-8
        # JSON spec says default is UTF-8, so always guess it
        # if we can't guess otherwise
        encoding = 'utf8'
    # Make sure the encoding is supported by Python
    try:
        cdk = codecs.lookup(encoding)
    except LookupError:
        if encoding.startswith('utf-32') \
               or encoding.startswith('ucs4') \
               or encoding.startswith('ucs-4'):
            # Python doesn't natively have a UTF-32 codec, but JSON
            # requires that it be supported.  So we must decode these
            # manually.
            if encoding.endswith('le'):
                unis = utf32le_decode(s)
            else:
                unis = utf32be_decode(s)
        else:
            raise JSONDecodeError('this python has no codec for this character encoding',encoding)
    else:
        # Convert to unicode using a standard codec
        unis = s.decode(encoding)
    return unis


def surrogate_pair_as_unicode( c1, c2 ):
    """Takes a pair of unicode surrogates and returns the equivalent unicode character.

    The input pair must be a surrogate pair, with c1 in the range
    U+D800 to U+DBFF and c2 in the range U+DC00 to U+DFFF.

    """
    n1, n2 = ord(c1), ord(c2)
    if n1 < 0xD800 or n1 > 0xDBFF or n2 < 0xDC00 or n2 > 0xDFFF:
        raise JSONDecodeError('illegal Unicode surrogate pair',(c1,c2))
    a = n1 - 0xD800
    b = n2 - 0xDC00
    v = (a << 10) | b
    v += 0x10000
    return unichr(v)


def unicode_as_surrogate_pair( c ):
    """Takes a single unicode character and returns a sequence of surrogate pairs.

    The output of this function is a tuple consisting of one or two unicode
    characters, such that if the input character is outside the BMP range
    then the output is a two-character surrogate pair representing that character.

    If the input character is inside the BMP then the output tuple will have
    just a single character...the same one.

    """
    n = ord(c)
    if n < 0x10000:
        return (unichr(n),)  # in BMP, surrogate pair not required
    v = n - 0x10000
    vh = (v >> 10) & 0x3ff   # highest 10 bits
    vl = v & 0x3ff  # lowest 10 bits
    w1 = 0xD800 | vh
    w2 = 0xDC00 | vl
    return (unichr(w1), unichr(w2))


# ----------------------------------------------------------------------
# Type identification

def isnumbertype( obj ):
    """Is the object of a Python number type (excluding complex)?"""
    return isinstance(obj, (int,long,float)) \
           and not isinstance(obj, bool) \
           or obj is nan or obj is inf or obj is neginf


def isstringtype( obj ):
    """Is the object of a Python string type?"""
    if isinstance(obj, basestring):
        return True
    # Must also check for some other pseudo-string types
    import types, UserString
    return isinstance(obj, types.StringTypes) \
           or isinstance(obj, UserString.UserString) \
           or isinstance(obj, UserString.MutableString)


# ----------------------------------------------------------------------
# Numeric helpers

def decode_hex( hexstring ):
    """Decodes a hexadecimal string into it's integer value."""
    # We don't use the builtin 'hex' codec in python since it can
    # not handle odd numbers of digits, nor raise the same type
    # of exceptions we want to.
    n = 0
    for c in hexstring:
        if '0' <= c <= '9':
            d = ord(c) - ord('0')
        elif 'a' <= c <= 'f':
            d = ord(c) - ord('a') + 10
        elif 'A' <= c <= 'F':
            d = ord(c) - ord('A') + 10
        else:
            raise JSONDecodeError('not a hexadecimal number',hexstring)
        # Could use ((n << 4 ) | d), but python 2.3 issues a FutureWarning.
        n = (n * 16) + d
    return n


def decode_octal( octalstring ):
    """Decodes an octal string into it's integer value."""
    n = 0
    for c in octalstring:
        if '0' <= c <= '7':
            d = ord(c) - ord('0')
        else:
            raise JSONDecodeError('not an octal number',octalstring)
        # Could use ((n << 3 ) | d), but python 2.3 issues a FutureWarning.
        n = (n * 8) + d
    return n


# ----------------------------------------------------------------------
# Exception classes.

class JSONError(ValueError):
    """Our base class for all JSON-related errors.

    """
    def pretty_description(self):
        err = self.args[0]
        if len(self.args) > 1:
            err += ': '
            for anum, a in enumerate(self.args[1:]):
                if anum > 1:
                    err += ', '
                astr = repr(a)
                if len(astr) > 20:
                    astr = astr[:20] + '...'
                err += astr
        return err

class JSONDecodeError(JSONError):
    """An exception class raised when a JSON decoding error (syntax error) occurs."""


class JSONEncodeError(JSONError):
    """An exception class raised when a python object can not be encoded as a JSON string."""


#----------------------------------------------------------------------
# The main JSON encoder/decoder class.

class JSON(object):
    """An encoder/decoder for JSON data streams.

    Usually you will call the encode() or decode() methods.  The other
    methods are for lower-level processing.

    Whether the JSON parser runs in strict mode (which enforces exact
    compliance with the JSON spec) or the more forgiving non-string mode
    can be affected by setting the 'strict' argument in the object's
    initialization; or by assigning True or False to the 'strict'
    property of the object.

    You can also adjust a finer-grained control over strictness by
    allowing or preventing specific behaviors.  You can get a list of
    all the available behaviors by accessing the 'behaviors' property.
    Likewise the allowed_behaviors and prevented_behaviors list which
    behaviors will be allowed and which will not.  Call the allow()
    or prevent() methods to adjust these.
    
    """
    _escapes_json = { # character escapes in JSON
        '"': '"',
        '/': '/',
        '\\': '\\',
        'b': '\b',
        'f': '\f',
        'n': '\n',
        'r': '\r',
        't': '\t',
        }

    _escapes_js = { # character escapes in Javascript
        '"': '"',
        '\'': '\'',
        '\\': '\\',
        'b': '\b',
        'f': '\f',
        'n': '\n',
        'r': '\r',
        't': '\t',
        'v': '\v',
        '0': '\x00'
        }

    # Following is a reverse mapping of escape characters, used when we
    # output JSON.  Only those escapes which are always safe (e.g., in JSON)
    # are here.  It won't hurt if we leave questionable ones out.
    _rev_escapes = {'\n': '\\n',
                    '\t': '\\t',
                    '\b': '\\b',
                    '\r': '\\r',
                    '\f': '\\f',
                    '"': '\\"',
                    '\\': '\\\\'}

    def __init__(self, strict=False, compactly=True, escape_unicode=False):
        """Creates a JSON encoder/decoder object.
        
        If 'strict' is set to True, then only strictly-conforming JSON
        output will be produced.  Note that this means that some types
        of values may not be convertable and will result in a
        JSONEncodeError exception.
        
        If 'compactly' is set to True, then the resulting string will
        have all extraneous white space removed; if False then the
        string will be "pretty printed" with whitespace and indentation
        added to make it more readable.
        
        If 'escape_unicode' is set to True, then all non-ASCII characters
        will be represented as a unicode escape sequence; if False then
        the actual real unicode character will be inserted if possible.

        The 'escape_unicode' can also be a function, which when called
        with a single argument of a unicode character will return True
        if the character should be escaped or False if it should not.
        
        If you wish to extend the encoding to ba able to handle
        additional types, you should subclass this class and override
        the encode_default() method.
        
        """
        import sys
        self._set_strictness(strict)
        self._encode_compactly = compactly
        try:
            # see if we were passed a predicate function
            b = escape_unicode(u'A')
            self._encode_unicode_as_escapes = escape_unicode
        except (ValueError, NameError, TypeError):
            # Just set to True or False.  We could use lambda x:True
            # to make it more consistent (always a function), but it
            # will be too slow, so we'll make explicit tests later.
            self._encode_unicode_as_escapes = bool(escape_unicode)
        self._sort_dictionary_keys = True

        # The following is a boolean map of the first 256 characters
        # which will quickly tell us which of those characters never
        # need to be escaped.

        self._asciiencodable = [32 <= c < 128 and not self._rev_escapes.has_key(chr(c))
                              for c in range(0,255)]

    def _set_strictness(self, strict):
        """Changes the strictness behavior.

        Pass True to be very strict about JSON syntax, or False to be looser.
        """
        self._allow_any_type_at_start = not strict
        self._allow_all_numeric_signs = not strict
        self._allow_comments = not strict
        self._allow_control_char_in_string = not strict
        self._allow_hex_numbers = not strict
        self._allow_initial_decimal_point = not strict
        self._allow_js_string_escapes = not strict
        self._allow_non_numbers = not strict
        self._allow_nonescape_characters = not strict  # "\z" -> "z"
        self._allow_nonstring_keys = not strict
        self._allow_omitted_array_elements = not strict
        self._allow_single_quoted_strings = not strict
        self._allow_trailing_comma_in_literal = not strict
        self._allow_undefined_values = not strict
        self._allow_unicode_format_control_chars = not strict
        self._allow_unicode_whitespace = not strict
        # Always disable this by default
        self._allow_octal_numbers = False

    def allow(self, behavior):
        """Allow the specified behavior (turn off a strictness check).

        The list of all possible behaviors is available in the behaviors property.
        You can see which behaviors are currently allowed by accessing the
        allowed_behaviors property.

        """
        p = '_allow_' + behavior
        if hasattr(self, p):
            setattr(self, p, True)
        else:
            raise AttributeError('Behavior is not known',behavior)

    def prevent(self, behavior):
        """Prevent the specified behavior (turn on a strictness check).

        The list of all possible behaviors is available in the behaviors property.
        You can see which behaviors are currently prevented by accessing the
        prevented_behaviors property.

        """
        p = '_allow_' + behavior
        if hasattr(self, p):
            setattr(self, p, False)
        else:
            raise AttributeError('Behavior is not known',behavior)

    def _get_behaviors(self):
        return sorted([ n[len('_allow_'):] for n in self.__dict__ \
                        if n.startswith('_allow_')])
    behaviors = property(_get_behaviors,
                         doc='List of known behaviors that can be passed to allow() or prevent() methods')

    def _get_allowed_behaviors(self):
        return sorted([ n[len('_allow_'):] for n in self.__dict__ \
                        if n.startswith('_allow_') and getattr(self,n)])
    allowed_behaviors = property(_get_allowed_behaviors,
                                 doc='List of known behaviors that are currently allowed')

    def _get_prevented_behaviors(self):
        return sorted([ n[len('_allow_'):] for n in self.__dict__ \
                        if n.startswith('_allow_') and not getattr(self,n)])
    prevented_behaviors = property(_get_prevented_behaviors,
                                   doc='List of known behaviors that are currently prevented')

    def _is_strict(self):
        return not self.allowed_behaviors
    strict = property(_is_strict, _set_strictness,
                      doc='True if adherence to RFC 4627 syntax is strict, or False is more generous ECMAScript syntax is permitted')


    def isws(self, c):
        """Determines if the given character is considered as white space.
        
        Note that Javscript is much more permissive on what it considers
        to be whitespace than does JSON.
        
        Ref. ECMAScript section 7.2

        """
        if not self._allow_unicode_whitespace:
            return c in ' \t\n\r'
        else:
            if not isinstance(c,unicode):
                c = unicode(c)
            if c in u' \t\n\r\f\v':
                return True
            import unicodedata
            return unicodedata.category(c) == 'Zs'

    def islineterm(self, c):
        """Determines if the given character is considered a line terminator.

        Ref. ECMAScript section 7.3

        """
        if c == '\r' or c == '\n':
            return True
        if c == u'\u2028' or c == u'\u2029': # unicodedata.category(c) in  ['Zl', 'Zp']
            return True
        return False

    def strip_format_control_chars(self, txt):
        """Filters out all Unicode format control characters from the string.

        ECMAScript permits any Unicode "format control characters" to
        appear at any place in the source code.  They are to be
        ignored as if they are not there before any other lexical
        tokenization occurs.  Note that JSON does not allow them.

        Ref. ECMAScript section 7.1.

        """
        import unicodedata
        txt2 = filter( lambda c: unicodedata.category(unicode(c)) != 'Cf',
                       txt )
        return txt2


    def decode_null(self, s, i=0):
        """Intermediate-level decoder for ECMAScript 'null' keyword.

        Takes a string and a starting index, and returns a Python
        None object and the index of the next unparsed character.

        """
        if i < len(s) and s[i:i+4] == 'null':
            return None, i+4
        raise JSONDecodeError('literal is not the JSON "null" keyword', s)

    def encode_undefined(self):
        """Produces the ECMAScript 'undefined' keyword."""
        return 'undefined'

    def encode_null(self):
        """Produces the JSON 'null' keyword."""
        return 'null'

    def decode_boolean(self, s, i=0):
        """Intermediate-level decode for JSON boolean literals.

        Takes a string and a starting index, and returns a Python bool
        (True or False) and the index of the next unparsed character.

        """
        if s[i:i+4] == 'true':
            return True, i+4
        elif s[i:i+5] == 'false':
            return False, i+5
        raise JSONDecodeError('literal value is not a JSON boolean keyword',s)

    def encode_boolean(self, b):
        """Encodes the Python boolean into a JSON Boolean literal."""
        if bool(b):
            return 'true'
        return 'false'

    def decode_number(self, s, i=0, imax=None):
        """Intermediate-level decoder for JSON numeric literals.

        Takes a string and a starting index, and returns a Python
        suitable numeric type and the index of the next unparsed character.

        The returned numeric type can be either of a Python int,
        long, or float.  In addition some special non-numbers may
        also be returned such as nan, inf, and neginf (technically
        which are Python floats, but have no numeric value.)

        Ref. ECMAScript section 8.5.

        """
        if imax is None:
            imax = len(s)
        # Detect initial sign character(s)
        if not self._allow_all_numeric_signs:
            if s[i] == '+' or (s[i] == '-' and i+1 < imax and \
                               s[i+1] in '+-'):
                raise JSONDecodeError('numbers in strict JSON may only have a single "-" as a sign prefix',s[i:])
        sign = +1
        j = i  # j will point after the sign prefix
        while j < imax and s[j] in '+-':
            if s[j] == '-': sign = sign * -1
            j += 1
        # Check for ECMAScript symbolic non-numbers
        if s[j:j+3] == 'NaN':
            if self._allow_non_numbers:
                return nan, j+3
            else:
                raise JSONDecodeError('NaN literals are not allowed in strict JSON')
        elif s[j:j+8] == 'Infinity':
            if self._allow_non_numbers:
                if sign < 0:
                    return neginf, j+8
                else:
                    return inf, j+8
            else:
                raise JSONDecodeError('Infinity literals are not allowed in strict JSON')
        elif s[j:j+2] in ('0x','0X'):
            if self._allow_hex_numbers:
                k = j+2
                while k < imax and s[k] in hexdigits:
                    k += 1
                n = sign * decode_hex( s[j+2:k] )
                return n, k
            else:
                raise JSONDecodeError('hexadecimal literals are not allowed in strict JSON',s[i:])
        else:
            # Decimal (or octal) number, find end of number.
            # General syntax is:  \d+[\.\d+][e[+-]?\d+]
            k = j   # will point to end of digit sequence
            could_be_octal = ( k+1 < imax and s[k] == '0' )  # first digit is 0
            decpt = None  # index into number of the decimal point, if any
            ept = None # index into number of the e|E exponent start, if any
            esign = '+' # sign of exponent
            sigdigits = 0 # number of significant digits (approx, counts end zeros)
            while k < imax and (s[k].isdigit() or s[k] in '.+-eE'):
                c = s[k]
                if c not in octaldigits:
                    could_be_octal = False
                if c == '.':
                    if decpt is not None or ept is not None:
                        break
                    else:
                        decpt = k-j
                elif c in 'eE':
                    if ept is not None:
                        break
                    else:
                        ept = k-j
                elif c in '+-':
                    if not ept:
                        break
                    esign = c
                else: #digit
                    if not ept:
                        sigdigits += 1
                k += 1
            number = s[j:k]  # The entire number as a string
            #print 'NUMBER IS: ', repr(number), ', sign', sign, ', esign', esign, \
            #      ', sigdigits', sigdigits, \
            #      ', decpt', decpt, ', ept', ept

            # Handle octal integers first as an exception.  If octal
            # is not enabled (the ECMAScipt standard) then just do
            # nothing and treat the string as a decimal number.
            if could_be_octal and self._allow_octal_numbers:
                n = sign * decode_octal( number )
                return n, k

            # A decimal number.  Do a quick check on JSON syntax restrictions.
            if number[0] == '.' and not self._allow_initial_decimal_point:
                raise JSONDecodeError('numbers in strict JSON must have at least one digit before the decimal point',s[i:])
            elif number[0] == '0' and \
                     len(number) > 1 and number[1].isdigit():
                if self._allow_octal_numbers:
                    raise JSONDecodeError('initial zero digit is only allowed for octal integers',s[i:])
                else:
                    raise JSONDecodeError('initial zero digit must not be followed by other digits (octal numbers are not permitted)',s[i:])
            # Make sure decimal point is followed by a digit
            if decpt is not None:
                if decpt+1 >= len(number) or not number[decpt+1].isdigit():
                    raise JSONDecodeError('decimal point must be followed by at least one digit',s[i:])
            # Determine the exponential part
            if ept is not None:
                if ept+1 >= len(number):
                    raise JSONDecodeError('exponent in number is truncated',s[i:])
                try:
                    exponent = int(number[ept+1:])
                except ValueError:
                    raise JSONDecodeError('not a valid exponent in number',s[i:])
                ##print 'EXPONENT', exponent
            else:
                exponent = 0
            # Try to make an int/long first.
            if decpt is None and exponent >= 0:
                # An integer
                if ept:
                    n = int(number[:ept])
                else:
                    n = int(number)
                n *= sign
                if exponent:
                    n *= 10**exponent
                if n == 0 and sign < 0:
                    # minus zero, must preserve negative sign so make a float
                    n = -0.0
            else:
                try:
                    if decimal and (abs(exponent) > float_maxexp or sigdigits > float_sigdigits):
                        try:
                            n = decimal.Decimal(number)
                            n = n.normalize()
                        except decimal.Overflow:
                            if sign<0:
                                n = neginf
                            else:
                                n = inf
                        else:
                            n *= sign
                    else:
                        n = float(number) * sign
                except ValueError:
                    raise JSONDecodeError('not a valid JSON numeric literal', s[i:j])
            return n, k

    def encode_number(self, n):
        """Encodes a Python numeric type into a JSON numeric literal.
        
        The special non-numeric values of float('nan'), float('inf')
        and float('-inf') are translated into appropriate JSON
        literals.
        
        Note that Python complex types are not handled, as there is no
        ECMAScript equivalent type.
        
        """
        if isinstance(n, complex):
            if n.imag:
                raise JSONEncodeError('Can not encode a complex number that has a non-zero imaginary part',n)
            n = n.real
        if isinstance(n, (int,long)):
            return str(n)
        if decimal and isinstance(n, decimal.Decimal):
            return str(n)
        global nan, inf, neginf
        if n is nan:
            return 'NaN'
        elif n is inf:
            return 'Infinity'
        elif n is neginf:
            return '-Infinity'
        elif isinstance(n, float):
            # Check for non-numbers.
            # In python nan == inf == -inf, so must use repr() to distinguish
            reprn = repr(n).lower()
            if ('inf' in reprn and '-' in reprn) or n == neginf:
                return '-Infinity'
            elif 'inf' in reprn or n is inf:
                return 'Infinity'
            elif 'nan' in reprn or n is nan:
                return 'NaN'
            return repr(n)
        else:
            raise TypeError('encode_number expected an integral, float, or decimal number type',type(n))

    def decode_string(self, s, i=0, imax=None):
        """Intermediate-level decoder for JSON string literals.

        Takes a string and a starting index, and returns a Python
        string (or unicode string) and the index of the next unparsed
        character.

        """
        if imax is None:
            imax = len(s)
        if imax < i+2 or s[i] not in '"\'':
            raise JSONDecodeError('string literal must be properly quoted',s[i:])
        closer = s[i]
        if closer == '\'' and not self._allow_single_quoted_strings:
            raise JSONDecodeError('string literals must use double quotation marks in strict JSON',s[i:])
        i += 1 # skip quote
        if self._allow_js_string_escapes:
            escapes = self._escapes_js
        else:
            escapes = self._escapes_json
        ccallowed = self._allow_control_char_in_string
        chunks = []
        _append = chunks.append
        done = False
        high_surrogate = None
        while i < imax:
            c = s[i]
            # Make sure a high surrogate is immediately followed by a low surrogate
            if high_surrogate and (i+1 >= imax or s[i:i+2] != '\\u'):
                raise JSONDecodeError('High unicode surrogate must be followed by a low surrogate',s[i:])
            if c == closer:
                i += 1 # skip end quote
                done = True
                break
            elif c == '\\':
                # Escaped character
                i += 1
                if i >= imax:
                    raise JSONDecodeError('escape in string literal is incomplete',s[i-1:])
                c = s[i]

                if '0' <= c <= '7' and self._allow_octal_numbers:
                    # Handle octal escape codes first so special \0 doesn't kick in yet.
                    # Follow Annex B.1.2 of ECMAScript standard.
                    if '0' <= c <= '3':
                        maxdigits = 3
                    else:
                        maxdigits = 2
                    for k in range(i, i+maxdigits+1):
                        if k >= imax or s[k] not in octaldigits:
                            break
                    n = decode_octal(s[i:k])
                    if n < 128:
                        _append( chr(n) )
                    else:
                        _append( unichr(n) )
                    i = k
                    continue

                if escapes.has_key(c):
                    _append(escapes[c])
                    i += 1
                elif c == 'u' or c == 'x':
                    i += 1
                    if c == 'u':
                        digits = 4
                    else: # c== 'x'
                        if not self._allow_js_string_escapes:
                            raise JSONDecodeError(r'string literals may not use the \x hex-escape in strict JSON',s[i-1:])
                        digits = 2
                    if i+digits >= imax:
                        raise JSONDecodeError('numeric character escape sequence is truncated',s[i-1:])
                    n = decode_hex( s[i:i+digits] )
                    if high_surrogate:
                        # Decode surrogate pair and clear high surrogate
                        _append( surrogate_pair_as_unicode( high_surrogate, unichr(n) ) )
                        high_surrogate = None
                    elif n < 128:
                        # ASCII chars always go in as a str
                        _append( chr(n) )
                    elif 0xd800 <= n <= 0xdbff: # high surrogate
                        if imax < i + digits + 2 or s[i+digits] != '\\' or s[i+digits+1] != 'u':
                            raise JSONDecodeError('High unicode surrogate must be followed by a low surrogate',s[i-2:])
                        high_surrogate = unichr(n)  # remember until we get to the low surrogate
                    elif 0xdc00 <= n <= 0xdfff: # low surrogate
                        raise JSONDecodeError('Low unicode surrogate must be proceeded by a high surrogate',s[i-2:])
                    else:
                        # Other chars go in as a unicode char
                        _append( unichr(n) )
                    i += digits
                else:
                    # Unknown escape sequence
                    if self._allow_nonescape_characters:
                        _append( c )
                        i += 1
                    else:
                        raise JSONDecodeError('unsupported escape code in JSON string literal',s[i-1:])
            elif ord(c) <= 0x1f: # A control character
                if self.islineterm(c):
                    raise JSONDecodeError('line terminator characters must be escaped inside string literals',s[i:])
                elif ccallowed:
                    _append( c )
                    i += 1
                else:
                    raise JSONDecodeError('control characters must be escaped inside JSON string literals',s[i:])
            else: # A normal character; not an escape sequence or end-quote.
                # Find a whole sequence of "safe" characters so we can append them
                # all at once rather than one a time, for speed.
                j = i
                i += 1
                while i < imax and s[i] not in unsafe_string_chars and s[i] != closer:
                    i += 1
                _append(s[j:i])
        if not done:
            raise JSONDecodeError('string literal is not terminated with a quotation mark',s)
        s = ''.join( chunks )
        return s, i

    def encode_string(self, s):
        """Encodes a Python string into a JSON string literal.

        """
        # Must handle instances of UserString specially in order to be
        # able to use ord() on it's simulated "characters".
        import UserString
        if isinstance(s, (UserString.UserString, UserString.MutableString)):
            def tochar(c):
                return c.data
        else:
            # Could use "lambda c:c", but that is too slow.  So we set to None
            # and use an explicit if test inside the loop.
            tochar = None
        
        chunks = []
        chunks.append('"')
        revesc = self._rev_escapes
        asciiencodable = self._asciiencodable
        encunicode = self._encode_unicode_as_escapes
        i = 0
        imax = len(s)
        while i < imax:
            if tochar:
                c = tochar(s[i])
            else:
                c = s[i]
            cord = ord(c)
            if cord < 256 and asciiencodable[cord] and isinstance(encunicode, bool):
                # Contiguous runs of plain old printable ASCII can be copied
                # directly to the JSON output without worry (unless the user
                # has supplied a custom is-encodable function).
                j = i
                i += 1
                while i < imax:
                    if tochar:
                        c = tochar(s[i])
                    else:
                        c = s[i]
                    cord = ord(c)
                    if cord < 256 and asciiencodable[cord]:
                        i += 1
                    else:
                        break
                chunks.append( unicode(s[j:i]) )
            elif revesc.has_key(c):
                # Has a shortcut escape sequence, like "\n"
                chunks.append(revesc[c])
                i += 1
            elif cord <= 0x1F:
                # Always unicode escape ASCII-control characters
                chunks.append(r'\u%04x' % cord)
                i += 1
            elif 0xD800 <= cord <= 0xDFFF:
                # A raw surrogate character!  This should never happen
                # and there's no way to include it in the JSON output.
                # So all we can do is complain.
                cname = 'U+%04X' % cord
                raise JSONEncodeError('can not include or escape a Unicode surrogate character',cname)
            elif cord <= 0xFFFF:
                # Other BMP Unicode character
                if isinstance(encunicode, bool):
                    doesc = encunicode
                else:
                    doesc = encunicode( c )
                if doesc:
                    chunks.append(r'\u%04x' % cord)
                else:
                    chunks.append( c )
                i += 1
            else: # ord(c) >= 0x10000
                # Non-BMP Unicode
                if isinstance(encunicode, bool):
                    doesc = encunicode
                else:
                    doesc = encunicode( c )
                if doesc:
                    for surrogate in unicode_as_surrogate_pair(c):
                        chunks.append(r'\u%04x' % ord(surrogate))
                else:
                    chunks.append( c )
                i += 1
        chunks.append('"')
        return ''.join( chunks )

    def skip_comment(self, txt, i=0):
        """Skips an ECMAScript comment, either // or /* style.

        The contents of the comment are returned as a string, as well
        as the index of the character immediately after the comment.

        """
        if i+1 >= len(txt) or txt[i] != '/' or txt[i+1] not in '/*':
            return None, i
        if not self._allow_comments:
            raise JSONDecodeError('comments are not allowed in strict JSON',txt[i:])
        multiline = (txt[i+1] == '*')
        istart = i
        i += 2
        while i < len(txt):
            if multiline:
                if txt[i] == '*' and i+1 < len(txt) and txt[i+1] == '/':
                    j = i+2
                    break
                elif txt[i] == '/' and i+1 < len(txt) and txt[i+1] == '*':
                    raise JSONDecodeError('multiline /* */ comments may not nest',txt[istart:i+1])
            else:
                if self.islineterm(txt[i]):
                    j = i  # line terminator is not part of comment
                    break
            i += 1

        if i >= len(txt):
            if not multiline:
                j = len(txt)  # // comment terminated by end of file is okay
            else:
                raise JSONDecodeError('comment was never terminated',txt[istart:])
        return txt[istart:j], j

    def skipws(self, txt, i=0, imax=None, skip_comments=True):
        """Skips whitespace.
        """
        if not self._allow_comments and not self._allow_unicode_whitespace:
            if imax is None:
                imax = len(txt)
            while i < imax and txt[i] in ' \r\n\t':
                i += 1
            return i
        else:
            return self.skipws_any(txt, i, imax, skip_comments)

    def skipws_any(self, txt, i=0, imax=None, skip_comments=True):
        """Skips all whitespace, including comments and unicode whitespace

        Takes a string and a starting index, and returns the index of the
        next non-whitespace character.

        If skip_comments is True and not running in strict JSON mode, then
        comments will be skipped over just like whitespace.

        """
        if imax is None:
            imax = len(txt)
        while i < imax:
            if txt[i] == '/':
                cmt, i = self.skip_comment(txt, i)
            if i < imax and self.isws(txt[i]):
                i += 1
            else:
                break
        return i

    def decode_composite(self, txt, i=0, imax=None):
        """Intermediate-level JSON decoder for composite literal types (array and object).

        Takes text and a starting index, and returns either a Python list or
        dictionary and the index of the next unparsed character.

        """
        if imax is None:
            imax = len(txt)
        i = self.skipws(txt, i, imax)
        starti = i
        if i >= imax or txt[i] not in '{[':
            raise JSONDecodeError('composite object must start with "[" or "{"',txt[i:])
        if txt[i] == '[':
            isdict = False
            closer = ']'
            obj = []
        else:
            isdict = True
            closer = '}'
            obj = {}
        i += 1 # skip opener
        i = self.skipws(txt, i, imax)

        if i < imax and txt[i] == closer:
            # empty composite
            i += 1
            done = True
        else:
            saw_value = False   # set to false at beginning and after commas
            done = False
            while i < imax:
                i = self.skipws(txt, i, imax)
                if i < imax and (txt[i] == ',' or txt[i] == closer):
                    c = txt[i]
                    i += 1
                    if c == ',':
                        if not saw_value:
                            # no preceeding value, an elided (omitted) element
                            if isdict:
                                raise JSONDecodeError('can not omit elements of an object (dictionary)')
                            if self._allow_omitted_array_elements:
                                if self._allow_undefined_values:
                                    obj.append( undefined )
                                else:
                                    obj.append( None )
                            else:
                                raise JSONDecodeError('strict JSON does not permit omitted array (list) elements',txt[i:])
                        saw_value = False
                        continue
                    else: # c == closer
                        if not saw_value and not self._allow_trailing_comma_in_literal:
                            if isdict:
                                raise JSONDecodeError('strict JSON does not allow a final comma in an object (dictionary) literal',txt[i-2:])
                            else:
                                raise JSONDecodeError('strict JSON does not allow a final comma in an array (list) literal',txt[i-2:])
                        done = True
                        break

                # Decode the item
                if isdict and self._allow_nonstring_keys:
                    r = self.decodeobj(txt, i, identifier_as_string=True)
                else:
                    r = self.decodeobj(txt, i, identifier_as_string=False)
                if r:
                    if saw_value:
                        # two values without a separating comma
                        raise JSONDecodeError('values must be separated by a comma', txt[i:r[1]])
                    saw_value = True
                    i = self.skipws(txt, r[1], imax)
                    if isdict:
                        key = r[0]  # Ref 11.1.5
                        if not isstringtype(key):
                            if isnumbertype(key):
                                if not self._allow_nonstring_keys:
                                    raise JSONDecodeError('strict JSON only permits string literals as object properties (dictionary keys)',txt[starti:])
                            else:
                                raise JSONDecodeError('object properties (dictionary keys) must be either string literals or numbers',txt[starti:])
                        if i >= imax or txt[i] != ':':
                            raise JSONDecodeError('object property (dictionary key) has no value, expected ":"',txt[starti:])
                        i += 1
                        i = self.skipws(txt, i, imax)
                        rval = self.decodeobj(txt, i)
                        if rval:
                            i = self.skipws(txt, rval[1], imax)
                            obj[key] = rval[0]
                        else:
                            raise JSONDecodeError('object property (dictionary key) has no value',txt[starti:])
                    else: # list
                        obj.append( r[0] )
                else: # not r
                    if isdict:
                        raise JSONDecodeError('expected a value, or "}"',txt[i:])
                    elif not self._allow_omitted_array_elements:
                        raise JSONDecodeError('expected a value or "]"',txt[i:])
                    else:
                        raise JSONDecodeError('expected a value, "," or "]"',txt[i:])
            # end while
        if not done:
            if isdict:
                raise JSONDecodeError('object literal (dictionary) is not terminated',txt[starti:])
            else:
                raise JSONDecodeError('array literal (list) is not terminated',txt[starti:])
        return obj, i

    def decode_javascript_identifier(self, name):
        """Convert a JavaScript identifier into a Python string object.

        This method can be overriden by a subclass to redefine how JavaScript
        identifiers are turned into Python objects.  By default this just
        converts them into strings.

        """
        return name

    def decodeobj(self, txt, i=0, imax=None, identifier_as_string=False, only_object_or_array=False):
        """Intermediate-level JSON decoder.

        Takes a string and a starting index, and returns a two-tuple consting
        of a Python object and the index of the next unparsed character.

        If there is no value at all (empty string, etc), the None is
        returned instead of a tuple.

        """
        if imax is None:
            imax = len(txt)
        obj = None
        i = self.skipws(txt, i, imax)
        if i >= imax:
            raise JSONDecodeError('Unexpected end of input')
        c = txt[i]

        if c == '[' or c == '{':
            obj, i = self.decode_composite(txt, i, imax)
        elif only_object_or_array:
            raise JSONDecodeError('JSON document must start with an object or array type only', txt[i:i+20])
        elif c == '"' or c == '\'':
            obj, i = self.decode_string(txt, i, imax)
        elif c.isdigit() or c in '.+-':
            obj, i = self.decode_number(txt, i, imax)
        elif c.isalpha() or c in'_$':
            j = i
            while j < imax and (txt[j].isalnum() or txt[j] in '_$'):
                j += 1
            kw = txt[i:j]
            if kw == 'null':
                obj, i = None, j
            elif kw == 'true':
                obj, i = True, j
            elif kw == 'false':
                obj, i = False, j
            elif kw == 'undefined':
                if self._allow_undefined_values:
                    obj, i = undefined, j
                else:
                    raise JSONDecodeError('strict JSON does not allow undefined elements',txt[i:])
            elif kw == 'NaN' or kw == 'Infinity':
                obj, i = self.decode_number(txt, i)
            else:
                if identifier_as_string:
                    obj, i = self.decode_javascript_identifier(kw), j
                else:
                    raise JSONDecodeError('unknown keyword or identifier',kw)
        else:
            raise JSONDecodeError('can not decode value',txt[i:])
        return obj, i



    def decode(self, txt):
        """Decodes a JSON-endoded string into a Python object."""
        if self._allow_unicode_format_control_chars:
            txt = self.strip_format_control_chars(txt)
        r = self.decodeobj(txt, 0, only_object_or_array=not self._allow_any_type_at_start)
        if not r:
            raise JSONDecodeError('can not decode value',txt)
        else:
            obj, i = r
            i = self.skipws(txt, i)
            if i < len(txt):
                raise JSONDecodeError('unexpected or extra text',txt[i:])
        return obj

    def encode(self, obj, nest_level=0):
        """Encodes the Python object into a JSON string representation.

        This method will first attempt to encode an object by seeing
        if it has a json_equivalent() method.  If so than it will
        call that method and then recursively attempt to encode
        the object resulting from that call.

        Next it will attempt to determine if the object is a native
        type or acts like a squence or dictionary.  If so it will
        encode that object directly.

        Finally, if no other strategy for encoding the object of that
        type exists, it will call the encode_default() method.  That
        method currently raises an error, but it could be overridden
        by subclasses to provide a hook for extending the types which
        can be encoded.

        """
        chunks = []
        self.encode_helper(chunks, obj, nest_level)
        return ''.join( chunks )

    def encode_helper(self, chunklist, obj, nest_level):
        #print 'encode_helper(chunklist=%r, obj=%r, nest_level=%r)'%(chunklist,obj,nest_level)
        if hasattr(obj, 'json_equivalent'):
            json = self.encode_equivalent( obj, nest_level=nest_level )
            if json is not None:
                chunklist.append( json )
                return
        if obj is None:
            chunklist.append( self.encode_null() )
        elif obj is undefined:
            if self._allow_undefined_values:
                chunklist.append( self.encode_undefined() )
            else:
                raise JSONEncodeError('strict JSON does not permit "undefined" values')
        elif isinstance(obj, bool):
            chunklist.append( self.encode_boolean(obj) )
        elif isinstance(obj, (int,long,float,complex)) or \
                 (decimal and isinstance(obj, decimal.Decimal)):
            chunklist.append( self.encode_number(obj) )
        elif isinstance(obj, basestring) or isstringtype(obj):
            chunklist.append( self.encode_string(obj) )
        else:
            self.encode_composite(chunklist, obj, nest_level)

    def encode_composite(self, chunklist, obj, nest_level):
        """Encodes just dictionaries, lists, or sequences.

        Basically handles any python type for which iter() can create
        an iterator object.

        This method is not intended to be called directly.  Use the
        encode() method instead.

        """
        #print 'encode_complex_helper(chunklist=%r, obj=%r, nest_level=%r)'%(chunklist,obj,nest_level)
        try:
            # Is it a dictionary or UserDict?  Try iterkeys method first.
            it = obj.iterkeys()
        except AttributeError:
            try:
                # Is it a sequence?  Try to make an iterator for it.
                it = iter(obj)
            except TypeError:
                it = None
        if it is not None:
            # Does it look like a dictionary?  Check for a minimal dict or
            # UserDict interface.
            isdict = hasattr(obj, '__getitem__') and hasattr(obj, 'keys')
            compactly = self._encode_compactly
            if isdict:
                chunklist.append('{')
                if compactly:
                    dictcolon = ':'
                else:
                    dictcolon = ' : '
            else:
                chunklist.append('[')
            #print nest_level, 'opening sequence:', repr(chunklist)
            if not compactly:
                indent0 = '  ' * nest_level
                indent = '  ' * (nest_level+1)
                chunklist.append(' ')
            sequence_chunks = []  # use this to allow sorting afterwards if dict
            try: # while not StopIteration
                numitems = 0
                while True:
                    obj2 = it.next()
                    if obj2 is obj:
                        raise JSONEncodeError('trying to encode an infinite sequence',obj)
                    if isdict and not isstringtype(obj2):
                        # Check JSON restrictions on key types
                        if isnumbertype(obj2):
                            if not self._allow_nonstring_keys:
                                raise JSONEncodeError('object properties (dictionary keys) must be strings in strict JSON',obj2)
                        else:
                            raise JSONEncodeError('object properties (dictionary keys) can only be strings or numbers in ECMAScript',obj2)

                    # Encode this item in the sequence and put into item_chunks
                    item_chunks = []
                    self.encode_helper( item_chunks, obj2, nest_level=nest_level+1 )
                    if isdict:
                        item_chunks.append(dictcolon)
                        obj3 = obj[obj2]
                        self.encode_helper(item_chunks, obj3, nest_level=nest_level+2)

                    #print nest_level, numitems, 'item:', repr(obj2)
                    #print nest_level, numitems, 'sequence_chunks:', repr(sequence_chunks)
                    #print nest_level, numitems, 'item_chunks:', repr(item_chunks)
                    #extend_list_with_sep(sequence_chunks, item_chunks)
                    sequence_chunks.append(item_chunks)
                    #print nest_level, numitems, 'new sequence_chunks:', repr(sequence_chunks)
                    numitems += 1
            except StopIteration:
                pass

            if isdict and self._sort_dictionary_keys:
                sequence_chunks.sort()  # Note sorts by JSON repr, not original Python object
            if compactly:
                sep = ','
            else:
                sep = ',\n' + indent

            #print nest_level, 'closing sequence'
            #print nest_level, 'chunklist:', repr(chunklist)
            #print nest_level, 'sequence_chunks:', repr(sequence_chunks)
            extend_and_flatten_list_with_sep( chunklist, sequence_chunks, sep )
            #print nest_level, 'new chunklist:', repr(chunklist)

            if not compactly:
                if numitems > 1:
                    chunklist.append('\n' + indent0)
                else:
                    chunklist.append(' ')
            if isdict:
                chunklist.append('}')
            else:
                chunklist.append(']')
        else: # Can't create an iterator for the object
            json2 = self.encode_default( obj, nest_level=nest_level )
            chunklist.append( json2 )

    def encode_equivalent( self, obj, nest_level=0 ):
        """This method is used to encode user-defined class objects.

        The object being encoded should have a json_equivalent()
        method defined which returns another equivalent object which
        is easily JSON-encoded.  If the object in question has no
        json_equivalent() method available then None is returned
        instead of a string so that the encoding will attempt the next
        strategy.

        If a caller wishes to disable the calling of json_equivalent()
        methods, then subclass this class and override this method
        to just return None.
        
        """
        if hasattr(obj, 'json_equivalent') \
               and callable(getattr(obj,'json_equivalent')):
            obj2 = obj.json_equivalent()
            if obj2 is obj:
                # Try to prevent careless infinite recursion
                raise JSONEncodeError('object has a json_equivalent() method that returns itself',obj)
            json2 = self.encode( obj2, nest_level=nest_level )
            return json2
        else:
            return None

    def encode_default( self, obj, nest_level=0 ):
        """This method is used to encode objects into JSON which are not straightforward.

        This method is intended to be overridden by subclasses which wish
        to extend this encoder to handle additional types.

        """
        raise JSONEncodeError('can not encode object into a JSON representation',obj)


# ------------------------------

def encode( obj, strict=False, compactly=True, escape_unicode=False, encoding=None ):
    """Encodes a Python object into a JSON-encoded string.

    If 'strict' is set to True, then only strictly-conforming JSON
    output will be produced.  Note that this means that some types
    of values may not be convertable and will result in a
    JSONEncodeError exception.

    If 'compactly' is set to True, then the resulting string will
    have all extraneous white space removed; if False then the
    string will be "pretty printed" with whitespace and indentation
    added to make it more readable.

    If 'escape_unicode' is set to True, then all non-ASCII characters
    will be represented as a unicode escape sequence; if False then
    the actual real unicode character will be inserted.

    If no encoding is specified (encoding=None) then the output will
    either be a Python string (if entirely ASCII) or a Python unicode
    string type.

    However if an encoding name is given then the returned value will
    be a python string which is the byte sequence encoding the JSON
    value.  As the default/recommended encoding for JSON is UTF-8,
    you should almost always pass in encoding='utf8'.

    """
    import sys
    encoder = None # Custom codec encoding function
    bom = None  # Byte order mark to prepend to final output
    cdk = None  # Codec to use
    if encoding is not None:
        import codecs
        try:
            cdk = codecs.lookup(encoding)
        except LookupError:
            cdk = None

        if cdk:
            pass
        elif not cdk:
            # No built-in codec was found, see if it is something we
            # can do ourself.
            encoding = encoding.lower()
            if encoding.startswith('utf-32') or encoding.startswith('utf32') \
                   or encoding.startswith('ucs4') \
                   or encoding.startswith('ucs-4'):
                # Python doesn't natively have a UTF-32 codec, but JSON
                # requires that it be supported.  So we must decode these
                # manually.
                if encoding.endswith('le'):
                    encoder = utf32le_encode
                elif encoding.endswith('be'):
                    encoder = utf32be_encode
                else:
                    encoder = utf32be_encode
                    bom = codecs.BOM_UTF32_BE
            elif encoding.startswith('ucs2') or encoding.startswith('ucs-2'):
                # Python has no UCS-2, but we can simulate with
                # UTF-16.  We just need to force us to not try to
                # encode anything past the BMP.
                encoding = 'utf-16'
                if not escape_unicode and not callable(escape_unicode):
                   escape_unicode = lambda c: (0xD800 <= ord(c) <= 0xDFFF) or ord(c) >= 0x10000
            else:
                raise JSONEncodeError('this python has no codec for this character encoding',encoding)

    if not escape_unicode and not callable(escape_unicode):
        if encoding and encoding.startswith('utf'):
            # All UTF-x encodings can do the whole Unicode repertoire, so
            # do nothing special.
            pass
        else:
            # Even though we don't want to escape all unicode chars,
            # the encoding being used may force us to do so anyway.
            # We must pass in a function which says which characters
            # the encoding can handle and which it can't.
            def in_repertoire( c, encoding_func ):
                try:
                    x = encoding_func( c, errors='strict' )
                except UnicodeError:
                    return False
                return True
            if encoder:
                escape_unicode = lambda c: not in_repertoire(c, encoder)
            elif cdk:
                escape_unicode = lambda c: not in_repertoire(c, cdk[0])
            else:
                pass # Let the JSON object deal with it

    j = JSON( strict=strict, compactly=compactly, escape_unicode=escape_unicode )

    unitxt = j.encode( obj )
    if encoder:
        txt = encoder( unitxt )
    elif encoding is not None:
        txt = unitxt.encode( encoding )
    else:
        txt = unitxt
    if bom:
        txt = bom + txt
    return txt


def decode( txt, strict=False, encoding=None, **kw ):
    """Decodes a JSON-encoded string into a Python object.

    If 'strict' is set to True, then those strings that are not
    entirely strictly conforming to JSON will result in a
    JSONDecodeError exception.

    The input string can be either a python string or a python unicode
    string.  If it is already a unicode string, then it is assumed
    that no character set decoding is required.

    However, if you pass in a non-Unicode text string (i.e., a python
    type 'str') then an attempt will be made to auto-detect and decode
    the character encoding.  This will be successful if the input was
    encoded in any of UTF-8, UTF-16 (BE or LE), or UTF-32 (BE or LE),
    and of course plain ASCII works too.
    
    Note though that if you know the character encoding, then you
    should convert to a unicode string yourself, or pass it the name
    of the 'encoding' to avoid the guessing made by the auto
    detection, as with

        python_object = demjson.decode( input_bytes, encoding='utf8' )

    Optional keywords arguments must be of the form
        allow_xxxx=True/False
    or
        prevent_xxxx=True/False
    where each will allow or prevent the specific behavior, after the
    evaluation of the 'strict' argument.  For example, if strict=True
    then by also passing 'allow_comments=True' then comments will be
    allowed.  If strict=False then prevent_comments=True will allow
    everything except comments.
    
    """
    # Initialize the JSON object
    j = JSON( strict=strict )
    for keyword, value in kw.items():
        if keyword.startswith('allow_'):
            behavior = keyword[6:]
            allow = bool(value)
        elif keyword.startswith('prevent_'):
            behavior = keyword[8:]
            allow = not bool(value)
        else:
            raise ValueError('unknown keyword argument', keyword)
        if allow:
            j.allow(behavior)
        else:
            j.prevent(behavior)

    # Convert the input string into unicode if needed.
    if isinstance(txt,unicode):
        unitxt = txt
    else:
        if encoding is None:
            unitxt = auto_unicode_decode( txt )
        else:
            cdk = None # codec
            decoder = None
            import codecs
            try:
                cdk = codecs.lookup(encoding)
            except LookupError:
                encoding = encoding.lower()
                decoder = None
                if encoding.startswith('utf-32') \
                       or encoding.startswith('ucs4') \
                       or encoding.startswith('ucs-4'):
                    # Python doesn't natively have a UTF-32 codec, but JSON
                    # requires that it be supported.  So we must decode these
                    # manually.
                    if encoding.endswith('le'):
                        decoder = utf32le_decode
                    elif encoding.endswith('be'):
                        decoder = utf32be_decode
                    else:
                        if txt.startswith( codecs.BOM_UTF32_BE ):
                            decoder = utf32be_decode
                            txt = txt[4:]
                        elif txt.startswith( codecs.BOM_UTF32_LE ):
                            decoder = utf32le_decode
                            txt = txt[4:]
                        else:
                            if encoding.startswith('ucs'):
                                raise JSONDecodeError('UCS-4 encoded string must start with a BOM')
                            decoder = utf32be_decode # Default BE for UTF, per unicode spec
                elif encoding.startswith('ucs2') or encoding.startswith('ucs-2'):
                    # Python has no UCS-2, but we can simulate with
                    # UTF-16.  We just need to force us to not try to
                    # encode anything past the BMP.
                    encoding = 'utf-16'

            if decoder:
                unitxt = decoder(txt)
            elif encoding:
                unitxt = txt.decode(encoding)
            else:
                raise JSONDecodeError('this python has no codec for this character encoding',encoding)

        # Check that the decoding seems sane.  Per RFC 4627 section 3:
        #    "Since the first two characters of a JSON text will
        #    always be ASCII characters [RFC0020], ..."
        #
        # This check is probably not necessary, but it allows us to
        # raise a suitably descriptive error rather than an obscure
        # syntax error later on.
        #
        # Note that the RFC requirements of two ASCII characters seems
        # to be an incorrect statement as a JSON string literal may
        # have as it's first character any unicode character.  Thus
        # the first two characters will always be ASCII, unless the
        # first character is a quotation mark.  And in non-strict
        # mode we can also have a few other characters too.
        if len(unitxt) > 2:
            first, second = unitxt[:2]
            if first in '"\'':
                pass # second can be anything inside string literal
            else:
                if ((ord(first) < 0x20 or ord(first) > 0x7f) or \
                    (ord(second) < 0x20 or ord(second) > 0x7f)) and \
                    (not j.isws(first) and not j.isws(second)):
                    # Found non-printable ascii, must check unicode
                    # categories to see if the character is legal.
                    # Only whitespace, line and paragraph separators,
                    # and format control chars are legal here.
                    import unicodedata
                    catfirst = unicodedata.category(unicode(first))
                    catsecond = unicodedata.category(unicode(second))
                    if catfirst not in ('Zs','Zl','Zp','Cf') or \
                           catsecond not in ('Zs','Zl','Zp','Cf'):
                        raise JSONDecodeError('the decoded string is gibberish, is the encoding correct?',encoding)
    # Now ready to do the actual decoding
    obj = j.decode( unitxt )
    return obj

# end file
