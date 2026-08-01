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
    max_tokens=4096,
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
A bulleted list of every URL found in the research.

Write in clear, professional, factual prose. Use Markdown bold (**like this**) for key terms
and Markdown headings (## and ###) exactly as specified above — do not just bold a line and
call it a heading."""),
])

writer_chain = writer_prompt | writer_llm | StrOutputParser()

#critic chain

critic_prompt = ChatPromptTemplate.from_messages([
     ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this exact format:

Score: X/10

Strengths:
- ...
- ...

Areas to Improve:
- ...
- ...

One line verdict:
..."""),
])

critic_chain = critic_prompt | llm | StrOutputParser()