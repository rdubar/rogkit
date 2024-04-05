import streamlit as st
from rogkit_package.media.plex_library import PlexLibrary
inport pandas as pd

st.set_page_config(page_title="RogKit", page_icon=":tools:")

st.header("Roger's Media Library")

df_full = PlexLibrary().get_df()



# get only the columns we want to display
# title, year, rating, genres, actors, writers, summary, section, platform, resolution, last_modified
df = df_full[['title', 'year', 'rating', 'genres', 'actors', 'writers', 'summary', 'section', 'platform', 'resolution', 'last_modified']]
movies_by_year = df['year'].value_counts().sort_index()
movies_by_decade = df['year'] // 10 * 10
movies_by_decade = movies_by_decade.value_counts().sort_index()
movies_by_genre = df['genres'].str.split(', ', expand=True).stack().value_counts()
# convert year to string
df['year'] = df['year'].astype(str)
# get rid of the .0 in the year
df['year'] = df['year'].str.replace('.0', '')


st.write(df)

# Graph the number of movies by year
st.subheader('Movies by Year')

st.bar_chart(movies_by_year)

# Graph the number of movies by decade
st.subheader('Movies by Decade')

st.bar_chart(movies_by_decade)

# Graph the number of movies by genre
st.subheader('Movies by Genre')
st.bar_chart(movies_by_genre)

