.. py:module:: amazoncaptcha.solver
.. py:currentmodule:: amazoncaptcha.solver

:py:mod:`~amazoncaptcha.solver` Module
======================================

This module contains the solver itself, AmazonCaptcha instance.

Examples
--------

Constructor usage.
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from amazoncaptcha import AmazonCaptcha

    captcha = AmazonCaptcha('captcha.jpg')
    solution = captcha.solve()

    # Or: solution = AmazonCaptcha('captcha.jpg').solve()

Using a selenium webdriver.
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from amazoncaptcha import AmazonCaptcha
    from selenium import webdriver

    driver = webdriver.Chrome() # This is a simplified example
    driver.get('https://www.amazon.com/errors/validateCaptcha')

    captcha = AmazonCaptcha.fromdriver(driver)
    solution = captcha.solve()

Using a captcha image link directly.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from amazoncaptcha import AmazonCaptcha

    link = 'https://images-na.ssl-images-amazon.com/captcha/usvmgloq/Captcha_kwrrnqwkph.jpg'

    captcha = AmazonCaptcha.fromlink(link)
    solution = captcha.solve()

Keeping logs of unsolved captcha.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from amazoncaptcha import AmazonCaptcha

    captcha = ...
    solution = captcha.solve(keep_logs=True)

The AmazonCaptcha Class
-----------------------

.. autoclass:: amazoncaptcha.solver.AmazonCaptcha
  :members:
