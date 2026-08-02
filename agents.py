from langchain.agents import create_agent
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import web_search, scrape_url
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatMistralAI(
    model="mistral-small-2506", #for testing purposes... I used free model
    api_key=os.getenv("MISTRAL_API_KEY"),
    temperature=0
)

# The writer needs a much bigger output budget than the search/reader
# agents — a 2-3 page report is roughly 1200-1800 words, which is easy to
# clip if max_tokens is left at whatever the provider's low default is.
writer_llm = ChatMistralAI(
    model="mistral-small-2506",
    api_key=os.getenv("MISTRAL_API_KEY"),
    temperature=0.3,   # a little room for fuller, less clipped prose than temperature=0
    max_tokens=8192,   # 4096 was cutting reports off mid-"Analysis & Implications" —
                        # a full 5-section, 1500-1800 word report with headers/formatting
                        # needs more headroom than that leaves.
)

# 1st agent
def build_search_agent():
    return create_agent(
        model=llm,
        tools=[web_search],
    )


# 2nd agent
def build_reader_agent():
    return create_agent(
        model=llm,
        tools=[scrape_url],
    )



#writer chain

writer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior research analyst who writes long-form, publication-quality reports "
     "for a professional audience. You never pad with filler, but you also never write a "
     "shallow summary — every claim gets explained, contextualized, and backed by specifics "
     "from the research provided. Your reports consistently run 1,200-1,800 words "
     "(roughly 2-3 pages) because the topic deserves real depth, not a bullet-point sketch."),
    ("human", """Write a comprehensive, in-depth research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

LENGTH REQUIREMENT: The report must be at least 1,200 words, ideally 1,500-1,800 words
(roughly 2-3 pages). Do not write a short summary — this is a full report. If the research
material is thin on a point, reason carefully about its implications and context rather than
stopping short; do not pad with repetition to hit the length.

Structure the report using Markdown with these sections:

## Introduction
2-3 paragraphs of context: what the topic is, why it matters right now, and what the report
will cover.

## Key Findings
At least 4-5 distinct findings, each as its own "### " subheading with 2-4 full paragraphs
of explanation underneath — not a one-line bullet. For each finding, explain what it means,
why it matters, and connect it to specifics (names, numbers, dates, examples) found in the
research.

## Analysis & Implications
2-3 paragraphs synthesizing what the findings mean together — trends, tensions between
sources, open questions, and what's likely to happen next.

## Conclusion
A substantive closing (not just a one-line summary) that ties the findings back to the
topic's significance.

## Sources
List EVERY distinct URL that appears anywhere in the "Research Gathered" section above —
both the search results block and the scraped source content — even ones you only drew
background context from rather than quoting directly. Do not skip a source just because you
didn't cite it word-for-word; if it's in the research, it belongs in this list.

Write in clear, professional, factual prose. Use Markdown bold (**like this**) for key terms
and Markdown headings (## and ###) exactly as specified above — do not just bold a line and
call it a heading."""),
])

writer_chain = writer_prompt | writer_llm | StrOutputParser()

#critic chain

critic_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a sharp, honest research editor. You are not here to be encouraging — you are "
     "here to be accurate. Most LLM critics default to a 'safe' 6-7/10 score out of politeness "
     "regardless of actual quality; you must actively resist that. Use the FULL 1-10 scale based "
     "on the rubric below, not just the middle of it."),
    ("human", """Review the research report below and give a short, sharp editor's note.

Report:
{report}

Scoring rubric — anchor your score to this, don't default to the middle:
- 9-10: Publication-ready. Deep, well-sourced, no real gaps.
- 7-8: Strong and usable, but with one or two clear gaps (e.g. thin sourcing on a claim,
  a section that's underdeveloped, minor repetition).
- 5-6: Adequate but noticeably shallow somewhere — weak sourcing, surface-level analysis,
  or a missing angle a reader would expect.
- 3-4: Real problems — thin research, unsupported claims, weak structure.
- 1-2: Not usable as-is.

Write your response as ONE short paragraph (3-5 sentences, no bullet points, no headers) that
naturally covers: the score, the single biggest strength, and the single biggest weakness —
in that order, as flowing prose. End with "Score: X/10" on its own line after the paragraph.
Be specific — name an actual section or claim, don't just say "could be more detailed."""),
])

critic_chain = critic_prompt | llm | StrOutputParser()