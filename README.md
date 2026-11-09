# Beyond the Soundtrack: Exploring the Interaction Between Music, Narrative, and Audience Reception in K-Dramas
## CS315, Fall 2026 - Kailyn, Anisa, Sophia

## Project Overview

This project explores the relationship between music, storytelling, and audience engagement in Korean television dramas (K-dramas). In particular, we examine whether dramas that place music at the center of their narratives differ from those that use music primarily as background accompaniment, and how viewers respond to music in these shows. Our project combines quantitative analysis of soundtrack popularity and audience engagement with qualitative analysis of online discussions to investigate how music contributes to the K-drama viewing experience.

## Research Questions (In Progress)

1. **RQ1:** To what extent is the popularity of original soundtracks associated with music-centered Korean dramas, in which music plays a significant role in the narrative?
2. **RQ2:** Within music-centered K-dramas, how does audience engagement differ between diegetic songs (performed by characters on screen) and non-diegetic background OST tracks?
3. **RQ3:** How do viewers discuss the role of music in music-centered K-dramas, and what themes emerge in their responses regarding the relationship between music, storytelling, and emotional engagement?

## Repository Structure

The repository is organized by project milestone and data collection stage.

### Milestone 2: Initial Dataset

Contains the initial dataset provided by Professor Eni Mustafaraj as a CSV export of a Google Sheet, along with an early notebook created by Sophia to identify potentially relevant dramas.

The dataset includes information such as:

- Drama titles in English and Korean
- Release year and original network
- Popularity rankings, scores, votes, and watchers
- Genres, episode counts, and tags
- Cast and production information
- Air dates, duration, content rating, and summaries
- Related content and alternate titles

The original discovery notebook is retained for reference, but its approach is no longer being used as the primary method for identifying music-centered dramas.

### Milestone 3: MDL Data Collection

Contains preliminary work using MyDramaList (MDL) to identify a more targeted sample of music-centered K-dramas.

The first notebook provides a reproducible workflow for:

1. Collecting candidate dramas from MDL search results.
2. Extracting drama titles, URLs, and available metadata.
3. Saving locally cached HTML pages to reduce repeated requests.
4. Organizing candidate dramas into a structured dataset.
5. Manually reviewing candidates to determine whether music plays a meaningful role in each drama's narrative.

The initial goal is to identify approximately 100–150 music-centered dramas. Keyword searches include terms such as *singer*, *idol*, *band*, *musician*, *guitarist*, *choir*, *busking*, and *musical*.

This dataset is preliminary and will be refined through manual screening.

## Data Collection and Analysis

The project will use multiple sources to examine different aspects of K-drama music and audience reception.

| Source | Purpose |
|---|---|
| MyDramaList (MDL) | Identify candidate dramas and collect drama-level metadata |
| Wiki Addicts | Collect drama synopses, cast-character mappings, OST information, and actor profiles |
| OST data | Examine track-level popularity and audience engagement |
| Online audience discussions | Analyze how viewers describe music's role in storytelling and emotional engagement |

**Note:** Diegetic and non-diegetic classifications will follow the project's operational definitions. In this project, diegetic songs refer specifically to songs performed by characters on screen, while non-diegetic songs refer to background OST tracks.

## Methodology

The project will follow a mixed-methods approach:

- **Quantitative analysis:** Compare OST popularity and audience engagement across music-centered and non-music-centered dramas, as well as between different types of songs within music-centered dramas.
- **Qualitative analysis:** Examine online audience discussions to identify recurring themes in how viewers perceive music's contribution to the narrative and emotional experience.
- **Comparative analysis:** Investigate whether the narrative prominence and use of music correspond with differences in soundtrack engagement.