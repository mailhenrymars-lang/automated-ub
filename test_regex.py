import re

# Test the regex pattern used in the share_post_by_link_handler function
link_pattern = r'https?://t\.me/(?:c/)?([^/]+)/(\d+)'

# Test cases
test_links = [
    'https://t.me/globalcryptogang/2354',
    'http://t.me/globalcryptogang/2354',
    'https://t.me/c/123456789/2354',
    'https://t.me/username/123'
]

for test_link in test_links:
    match = re.match(link_pattern, test_link)
    print(f"Link: {test_link}")
    print(f"Match: {match is not None}")
    if match:
        print(f"Groups: {match.groups()}")
    print("---")