"""Local AI categorization.

Pipeline for new or not yet categorized transactions:

1. **Rules** (app/rules.py) always take precedence.
2. **Classifier** (classifier.py): TF-IDF over payee, booking text and purpose
   plus amount features, logistic regression. It learns from all manual
   assignments and rule matches of the household and starts with a set of
   built-in examples (examples.py). If it is confident enough it assigns the
   category, otherwise the category is kept as a suggestion.
3. **Language model** (llm.py, optional): uncertain cases are sent to a local
   model in Ollama in the background.

Every manual assignment triggers a retraining in the background
(service.py). None of this leaves your own server.
"""
