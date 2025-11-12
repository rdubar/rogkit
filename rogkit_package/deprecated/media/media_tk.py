"""
Tkinter GUI for Plex media library search.

Simple desktop application for searching and browsing Plex media library.
"""
import tkinter as tk  # type: ignore
from tkinter import scrolledtext  # type: ignore

# Assuming these are available from your project's structure
from .plex_library import PlexLibrary
from .media_records import PlexRecordORM

plex_library = PlexLibrary()


def get_results(search_query):
    """Search Plex library and return formatted results string with count."""
    results = plex_library.search(search_query)
    # Handling the case where search_query is empty to return all results
    results_list = [result.title for result in results]
    results_sorted = sorted(results_list)
    results_str = '\n'.join(results_sorted)
    return results_str, len(results_sorted)  # Also return the number of results

class SearchApp:
    """Tkinter application for searching Plex media library."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Rog's Media Library")

        # Create a frame for the search box and button
        self.search_frame = tk.Frame(self.root)
        self.search_frame.pack(padx=10, pady=10)

        # Create the search entry box
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Bind the Enter key to the perform_search method
        self.search_entry.bind('<Return>', self.perform_search)  # Add this line

        # Create the search button
        self.search_button = tk.Button(self.search_frame, text="Search", command=self.perform_search)
        self.search_button.pack(side=tk.LEFT)

        # Create a clear search button
        self.clear_button = tk.Button(self.search_frame, text="Clear", command=self.clear_search)
        self.clear_button.pack(side=tk.LEFT)

        # Create a scrolled text area for displaying search results
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=60, height=10)
        self.text_area.pack(padx=10, pady=10)
        self.text_area.config(state=tk.DISABLED)  # Initially disable editing of the text area

        # Create a status label to show the number of items or matches
        self.status_label = tk.Label(self.root, text="Loading...")
        self.status_label.pack(padx=10, pady=5)

        # Display all items on startup
        self.perform_search()

    def perform_search(self, event=None):
        """Execute search and display results in text area."""
        search_query = self.search_var.get()
        self.text_area.config(state=tk.NORMAL)  # Enable editing to update text
        self.text_area.delete(1.0, tk.END)  # Clear existing text
        total = plex_library.total_records()
        results, num_results = get_results(search_query)
        self.text_area.insert(tk.END, results)
        self.text_area.config(state=tk.DISABLED)  # Disable editing after updating the text
        # Update the status label with the number of items or matches
        if search_query:
            self.status_label.config(text=f"{num_results:,} item(s) found for '{search_query}' from {total:,} results.")
        else:
            self.status_label.config(text=f"{total:,} item(s) found.")

    def clear_search(self):
        """Clear search box and show all results."""
        self.search_var.set('')  # Clear the search entry box
        self.perform_search()  # Perform an empty search to show all items

if __name__ == "__main__":
    root = tk.Tk()
    app = SearchApp(root)
    root.mainloop()
