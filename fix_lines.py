with open('scripts/entropy.py', 'r') as f:
    text = f.read()

# Fix the broken string splitting
text = text.replace("content.split('\n')", "content.split('\\n')")

with open('scripts/entropy.py', 'w') as f:
    f.write(text)
