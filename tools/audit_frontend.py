import re
import sys

def audit_html():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Tìm tất cả ID được định nghĩa trong HTML
    defined_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_\-]+)["\']', html))

    # 2. Tìm tất cả ID được gọi trong getElementById
    used_ids = set(re.findall(r'getElementById\(["\']([a-zA-Z0-9_\-]+)["\']\)', html))

    missing_ids = used_ids - defined_ids
    print('1. Tổng số ID định nghĩa:', len(defined_ids))
    print('   Tổng số ID được getElementById gọi:', len(used_ids))
    print('   Missing IDs referenced by getElementById:', missing_ids)

    # 3. Tìm tất cả function được gọi trong inline event handlers
    inline_handlers = re.findall(r'on(?:click|change|keyup|submit|input)=["\']\s*([a-zA-Z0-9_]+)\(', html)
    defined_functions = set(re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', html))
    defined_functions.update(re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', html))
    defined_functions.update(re.findall(r'async\s+function\s+([a-zA-Z0-9_]+)\s*\(', html))

    missing_functions = set(inline_handlers) - defined_functions
    print('\n2. Tổng số inline handlers:', len(inline_handlers))
    print('   Tổng số functions định nghĩa:', len(defined_functions))
    print('   Missing functions referenced by event handlers:', missing_functions)

if __name__ == '__main__':
    audit_html()
