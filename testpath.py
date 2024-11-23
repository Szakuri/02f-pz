import os

# Wyświetl wszystkie ścieżki w PATH
print("PATH:")
for path in os.environ["PATH"].split(";"):
    print(path)
