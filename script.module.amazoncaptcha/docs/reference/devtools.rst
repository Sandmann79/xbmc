.. py:module:: amazoncaptcha.devtools
.. py:currentmodule:: amazoncaptcha.devtools

:py:mod:`~amazoncaptcha.devtools` Module
========================================

This module contains the developer tools for both users and library contributors.

Examples
--------

Collect captcha.
^^^^^^^^^^^^^^^^

.. code-block:: python

    from amazoncaptcha import AmazonCaptchaCollector

    output_folder_path = 'path/to/folder'
    simultaneous_processes = 4
    target = 200

    collector = AmazonCaptchaCollector(output_folder_path)
    collector.start(target, simultaneous_processes)

Proceed accuracy tests.
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from amazoncaptcha import AmazonCaptchaCollector

    output_folder_path = 'path/to/folder'
    simultaneous_processes = 4
    target = 200

    collector = AmazonCaptchaCollector(output_folder_path, accuracy_test=True)
    collector.start(target, simultaneous_processes)

The AmazonCaptchaCollector Class
--------------------------------

.. autoclass:: amazoncaptcha.devtools.AmazonCaptchaCollector
  :members:
