import os
import sys
import argparse

def collate_files(directory, output_file="collated.txt"):
    """Recursively collates all text and code files from a given directory into one file."""
    count = 0
    with open(output_file, "w", encoding="utf-8") as out_file:
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Only include text and coding files based on extension
                if file.endswith((".txt", ".py", ".java", ".cpp", ".html", ".css", ".js", ".json", ".md")):
                    out_file.write(f"\n--- {file_path} ---\n")
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            out_file.write(f.read() + "\n")
                            count += 1
                    except Exception as e:
                        out_file.write(f"[Error reading file: {e}]\n")
    return count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collate text and code files from a directory into one file.")
    parser.add_argument("-p", "--path", nargs="?", type=str, default=None, help="Path of the directory to collate files from.")
    parser.add_argument("-o", "--output", type=str, help="Output file name.", default="collated.txt")
    args = parser.parse_args()
    
    if not args.path:
        args.path = os.getcwd()
    
    # Validate path
    if not os.path.exists(args.path):
        print("The specified path does not exist.")
        sys.exit(1)
    
    print(f"Collating files from: {args.path} to {args.output}")
    count = collate_files(args.path, args.output)
    if count == 0:
        print("No text or code files found.")
        sys.exit(1)
    
    print(f"{count} files collated into: {args.output}")
