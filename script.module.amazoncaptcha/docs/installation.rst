Installation
============

Warnings
--------

.. warning:: AmazonCaptcha uses Pillow library to operate the images. Pillow and PIL cannot co-exist in the same environment. Before installing AmazonCaptcha (which will automatically install Pillow), please, uninstall PIL.

Python Support
--------------

AmazonCaptcha supports the versions of Python according to the table below.

+-------------------------+--------+-------+-------+-------+-------+-------+
| **Python**              |**3.10**|**3.9**|**3.8**|**3.7**|**3.6**|**3.5**|
+-------------------------+--------+-------+-------+-------+-------+-------+
| AmazonCaptcha >= 0.5.3  |  Yes   |  Yes  |  Yes  |  Yes  |  No   |  No   |
+-------------------------+--------+-------+-------+-------+-------+-------+
| AmazonCaptcha <= 0.5.2  |  Yes   |  Yes  |  Yes  |  Yes  |  Yes  |  No   |
+-------------------------+--------+-------+-------+-------+-------+-------+

Basic Installation
------------------

Install AmazonCaptcha from PyPi with :command:`pip`:

    pip install amazoncaptcha

Install AmazonCaptcha from GitHub with :command:`git` and :command:`pip`:

    pip install git+https://github.com/a-maliarov/amazoncaptcha.git

Install AmazonCaptcha from GitHub after :command:`git clone`:

    python setup.py install
