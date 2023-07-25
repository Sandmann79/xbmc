+ **Version 0.0.10**:
  1. Reached 10000 training samples.
  2. Reached 90%+ accuracy.
+ **Version 0.0.11**:
  1. Fixed error with captcha images that were taken from BytesIO.
+ **Version 0.0.12**:
  1. Code adjustments and improvements.
  2. Program can now solve images where last letter is corrupted.
+ **Version 0.0.13**:
  1. Added and tested 'from_webdriver' classmethod.
+ **Version 0.1.0**:
  1. 100,000 captchas crash test, accuracy is 98.5%.
+ **Version 0.1.1 - 0.1.5**:
  1. Code adjustments and improvements.
  2. Added tests.
+ **Version 0.2.0**:
  1. Second crash test through 120k+ captchas.
  2. Accuracy increased to 99.1%
  3. Code coverage is 100%
+ **Version 0.3.0**:
  1. Program can now solve images where letters are intercepted.
  2. Third crash test through 140k+ captchas.
  3. Accuracy increased to 99.998%
+ **Version 0.3.8**:
  1. Added new instance - AmazonCaptchaCollector.
+ **Version 0.4.0**:
  1. Update docstring to Google style
  2. Deprecate class method `from_webdriver` to `fromdriver`
  3. Add `fromlink` class method
  4. Move utilities into a separated file
  5. Add `ContentTypeError` exception
+ **Version 0.5.0**:
  1. Remove captchas folder to the separated repository to lower the weight of this one
  2. Add Python 3.9 support
  3. Add Chromedriver 86.0.4240.22 support
  4. Update AmazonCaptchaCollector
  5. Add documentation.
  6. Add Pillow 8.0.0 support
  7. Add Stale Bot to remove stale issues
  8. Workflow update
+ **Version 0.5.1**:
  1. Add Chromedriver 91.0.4472.101 support
  2. Add Pillow 8.2.0 support
+ **Version 0.5.2**:
  1. Add Pillow 8.3.0 support
+ **Version 0.5.3**:
  1. Add Chromedriver 97.0.4692.71 support
  2. Add Pillow 9.0.0 support
  3. Add Python 3.10-dev support
  4. Drop Python 3.6 support
  5. Remove `from_webdriver` method
+ **Version 0.5.4**:
  1. 200,000 captchas crash test, accuracy is 100%.
  2. Minor notes added.
+ **Version 0.5.6**:
  1. Remove `selenium` from required dependencies.
+ **Version 0.5.10**:
  1. Add timeout to `AmazonCaptcha.fromlink` method.
