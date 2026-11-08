# Prompt templates and guardrails

These are the prompt patterns the answer service uses when it drafts a
reply. The mock client fills them from retrieved sources only; a real
client would use the same text as its system and user prompts.

## Short reply (default, `response_style: short`)

> Hello, thank you for writing about your {category} issue
> (priority: {priority}). Based on "{article title}": {article snippet}
> Please follow those steps and let us know if it helps.

## Detailed reply (`response_style: detailed`, or canary)

> Hello, thank you for writing about your {category} issue
> (priority: {priority}). Based on "{article title}": {article snippet}
> Here is what to do next, step by step, following that article. If the
> steps do not fix it, reply to this ticket and a support agent will take
> over. Related articles: {article titles}.

## Retrieval rule

Retrieve the top 2 knowledge-base articles by keyword overlap (with light
stemming) before drafting. Draft only from those articles. Quote the
article title so the reader can check the source.

## Guardrails

1. **Never invent an answer.** If no article was retrieved, reply:
   "I could not find a knowledge-base article that answers this question,
   so I will not guess. A support agent will review your ticket."
2. **Never use information that is not in a retrieved article.** No
   prices, dates, policies or steps beyond what the article says.
3. **Never ask for sensitive information.** No full card numbers, no
   passwords. The billing article already says the last four digits are
   enough.
4. **Keep the category and priority from the prediction service.** The
   draft does not re-decide them.
5. **One reply per ticket.** A repeated `request_id` returns the stored
   draft instead of drafting again.
