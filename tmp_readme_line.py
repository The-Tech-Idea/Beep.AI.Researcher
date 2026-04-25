with open('README.md', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'enhancement_plan.md' in line:
            print(i)
            break
