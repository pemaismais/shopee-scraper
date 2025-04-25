import logging
def _convert_shortened_number(text):
    """Converts strings like '1,2k' or '15k' or '1,2mil' or '15mil' to integer."""
    text = text.lower().strip()
    multiplier = 1
    if 'k' in text:
        multiplier = 1000
        text = text.replace('k', '')
    elif 'mil' in text:
        multiplier = 1000
        text = text.replace('mil', '')
        
    try:
        # Handle decimal numbers with comma like '1,2'
        if ',' in text:
            num_str = text.replace(',', '.')
        else:
            num_str = text
        num = float(num_str)
        return int(num * multiplier)
    except ValueError:
        logging.warning(f"Could not parse number from text: '{text}'")
        return 0
    