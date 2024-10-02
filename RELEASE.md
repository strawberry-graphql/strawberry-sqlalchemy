Release type: patch

Resolved an issue with the BigInt scalar definition, ensuring compatibility with Python 3.8 and 3.9. The missing name parameter was added to prevent runtime errors.
Fixed failing CI tests by updating the GitHub Actions workflow to improve test stability.
