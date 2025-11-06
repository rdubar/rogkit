"""
Wikipedia search and article fetcher.

Queries Wikipedia for articles and returns summaries or full content,
with handling for disambiguation and missing pages.
"""
import argparse
import wikipedia  # type: ignore


def search_wikipedia(search_term, full_article=False):
    """Search Wikipedia and return summary or full article."""
    try:
        # Search for the page
        page = wikipedia.summary(search_term) 
        
        # Return the full text if requested, otherwise return the summary
        return page.content if full_article else page.summary
    except wikipedia.exceptions.DisambiguationError as e:
        return f"Disambiguation error. Options include: {e.options}"
    except wikipedia.exceptions.PageError:
        return "Page not found."

def main():
    """CLI entry point for Wikipedia search."""
    parser = argparse.ArgumentParser(description="Fetch information from Wikipedia.")
    parser.add_argument("search_term", nargs='+', help="Search term for querying Wikipedia")
    parser.add_argument("-f", "--full", action="store_true", help="Fetch the full article instead of the summary")
    args = parser.parse_args()

    # Join the search terms into a single string
    search_query = ' '.join(args.search_term)
    
    print(f"Searching Wikipedia for: {search_query}")

    result = search_wikipedia(search_query, args.full)
    print(result)

if __name__ == "__main__":
    main()
