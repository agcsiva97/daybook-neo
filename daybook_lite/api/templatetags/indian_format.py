from django import template

register = template.Library()

@register.filter
def indian_format(value):
    try:
        value = float(value)
        is_negative = value < 0
        value = abs(value)

        # Split into integer and decimal parts
        integer_part = int(value)
        decimal_part = round(value - integer_part, 2)
        decimal_str = f'{decimal_part:.2f}'[1:]  # gives .00, .50 etc

        # Indian formatting logic
        # Last 3 digits first, then groups of 2
        s = str(integer_part)
        if len(s) <= 3:
            result = s
        else:
            last3 = s[-3:]
            remaining = s[:-3]
            # Group remaining digits in pairs from right
            pairs = []
            while len(remaining) > 2:
                pairs.append(remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                pairs.append(remaining)
            pairs.reverse()
            result = ','.join(pairs) + ',' + last3

        formatted = f'{result}{decimal_str}'
        return f'{formatted}' if is_negative else formatted

    except (ValueError, TypeError):
        return value