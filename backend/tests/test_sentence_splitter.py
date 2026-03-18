"""TDD tests for the streaming SentenceSplitter.

The SentenceSplitter accumulates streaming text tokens and yields complete
sentences for the TTS pipeline. It handles:
- Sentence boundary detection (.!? followed by whitespace)
- Abbreviation preservation (Dr., Mrs., Mr., etc.)
- Decimal number preservation (3.14, $125.00)
- Minimum chunk length batching (short fragments held until threshold)
- Newline boundaries
- Ellipsis preservation
- Token-by-token streaming simulation
- flush() for remaining text at end of stream
"""


from backend.app.services.sentence_splitter import SentenceSplitter


class TestSentenceSplitterBasicSplitting:
    """Basic sentence boundary detection."""

    def test_splits_on_period_followed_by_space(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Hello world. How are you? ")
        assert "Hello world." in result
        assert "How are you?" in result

    def test_splits_on_question_mark(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("How are you? I am fine. ")
        assert "How are you?" in result
        assert "I am fine." in result

    def test_splits_on_exclamation_mark(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Great news! We are open today. ")
        assert "Great news!" in result
        assert "We are open today." in result

    def test_multiple_sentences_in_one_push(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("First sentence here. Second sentence here. Third one! ")
        assert len(result) >= 2
        assert result[0] == "First sentence here."
        assert result[1] == "Second sentence here."

    def test_no_split_without_trailing_space(self):
        """Period at end of buffer without trailing space shouldn't split yet."""
        s = SentenceSplitter(min_length=10)
        result = s.push("Hello world.")
        assert result == []

    def test_split_on_newline_boundary(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("First line here\nSecond line here. ")
        assert len(result) >= 1
        assert "First line here" in result[0]


class TestSentenceSplitterAbbreviations:
    """Abbreviation handling — should NOT split on abbreviation periods."""

    def test_preserves_dr_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Dr. Martinez will see you now. ")
        assert result == ["Dr. Martinez will see you now."]

    def test_preserves_mrs_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Mrs. Jones is here. She left a message. ")
        # Should NOT split on "Mrs." — first real sentence boundary is "here."
        assert result[0] == "Mrs. Jones is here."

    def test_preserves_mr_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Mr. Brown will arrive soon. He is expected at noon. ")
        assert result[0] == "Mr. Brown will arrive soon."

    def test_preserves_ms_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Ms. Olivia is the assistant. She helps parents. ")
        assert result[0] == "Ms. Olivia is the assistant."

    def test_preserves_prof_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("Prof. Williams teaches science. The class starts at nine. ")
        assert result[0] == "Prof. Williams teaches science."

    def test_preserves_st_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("We are located on St. Main Street. Please visit us. ")
        assert result[0] == "We are located on St. Main Street."

    def test_preserves_vs_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("It is indoor vs. outdoor play. Both are great options. ")
        assert result[0] == "It is indoor vs. outdoor play."

    def test_preserves_am_pm_abbreviation(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("We open at 7 a.m. in the morning. Please arrive on time. ")
        assert result[0] == "We open at 7 a.m. in the morning."


class TestSentenceSplitterEdgeCases:
    """Edge cases: decimals, ellipsis, empty input."""

    def test_preserves_decimal_numbers(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("The fee is $125.00 per week. Payment is due Monday. ")
        # Should NOT split on "125.00" — the real boundary is "week."
        assert result[0] == "The fee is $125.00 per week."

    def test_preserves_decimal_in_sentence(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("The temperature is 98.6 degrees. That is normal. ")
        # Should NOT split on "98.6" — the real boundary is "degrees."
        assert result[0] == "The temperature is 98.6 degrees."

    def test_empty_push_returns_empty(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("")
        assert result == []

    def test_whitespace_only_push(self):
        s = SentenceSplitter(min_length=10)
        result = s.push("   ")
        assert result == []

    def test_preserves_ellipsis(self):
        """Ellipsis (...) should not split."""
        s = SentenceSplitter(min_length=10)
        result = s.push("Well... let me think about that. ")
        assert result == ["Well... let me think about that."]


class TestSentenceSplitterMinLength:
    """Minimum length batching — short fragments held until threshold."""

    def test_batches_short_sentences(self):
        s = SentenceSplitter(min_length=30)
        result = s.push("Hi. ")
        assert result == []  # "Hi." is only 3 chars, below min_length=30

    def test_releases_when_min_length_reached(self):
        s = SentenceSplitter(min_length=30)
        s.push("Hi. ")
        result = s.push("Welcome to Sunshine Learning Center. ")
        # Combined "Hi. Welcome to Sunshine Learning Center." exceeds 30 chars
        assert len(result) >= 1

    def test_min_length_zero_splits_everything(self):
        s = SentenceSplitter(min_length=0)
        result = s.push("Hi. Ok. ")
        assert len(result) >= 1

    def test_default_min_length_is_30(self):
        s = SentenceSplitter()
        assert s._min_length == 30


class TestSentenceSplitterFlush:
    """flush() returns remaining buffer content."""

    def test_flush_returns_remaining_text(self):
        s = SentenceSplitter(min_length=10)
        s.push("Hello world")
        remaining = s.flush()
        assert remaining == "Hello world"

    def test_flush_returns_none_when_empty(self):
        s = SentenceSplitter(min_length=10)
        remaining = s.flush()
        assert remaining is None

    def test_flush_returns_none_after_all_split(self):
        s = SentenceSplitter(min_length=10)
        s.push("Complete sentence. ")
        remaining = s.flush()
        # Either the sentence was yielded from push() leaving nothing,
        # or flush returns whatever is left
        # After "Complete sentence. " the buffer has trailing space
        # which should flush as None (stripped)
        assert remaining is None or remaining == "Complete sentence."

    def test_flush_clears_buffer(self):
        s = SentenceSplitter(min_length=10)
        s.push("Some text here")
        s.flush()
        assert s.flush() is None  # Second flush returns nothing

    def test_flush_returns_short_remainder(self):
        """Even if below min_length, flush always returns remaining text."""
        s = SentenceSplitter(min_length=100)
        s.push("Short text. ")
        remaining = s.flush()
        assert remaining is not None
        assert "Short text" in remaining


class TestSentenceSplitterStreaming:
    """Simulate token-by-token streaming from LLM."""

    def test_token_by_token_accumulation(self):
        s = SentenceSplitter(min_length=10)
        all_sentences = []
        text = "Hello world. How are you today? I am fine thanks. "
        for char in text:
            all_sentences.extend(s.push(char))
        remaining = s.flush()
        if remaining:
            all_sentences.append(remaining)
        assert "Hello world." in all_sentences
        assert "How are you today?" in all_sentences

    def test_word_by_word_streaming(self):
        s = SentenceSplitter(min_length=10)
        all_sentences = []
        words = [
            "Welcome ",
            "to ",
            "Sunshine ",
            "Learning ",
            "Center. ",
            "We ",
            "are ",
            "happy ",
            "to ",
            "help. ",
        ]
        for word in words:
            all_sentences.extend(s.push(word))
        remaining = s.flush()
        if remaining:
            all_sentences.append(remaining)
        assert len(all_sentences) >= 1
        assert "Welcome to Sunshine Learning Center." in all_sentences

    def test_multi_chunk_with_abbreviations(self):
        s = SentenceSplitter(min_length=10)
        all_sentences = []
        chunks = ["Dr. ", "Smith ", "is ", "available. ", "Call ", "now. "]
        for chunk in chunks:
            all_sentences.extend(s.push(chunk))
        remaining = s.flush()
        if remaining:
            all_sentences.append(remaining)
        assert "Dr. Smith is available." in all_sentences

    def test_streaming_preserves_sentence_order(self):
        s = SentenceSplitter(min_length=10)
        all_sentences = []
        text = "First sentence. Second sentence. Third sentence. "
        for char in text:
            all_sentences.extend(s.push(char))
        remaining = s.flush()
        if remaining:
            all_sentences.append(remaining)
        assert all_sentences[0] == "First sentence."
        assert all_sentences[1] == "Second sentence."
