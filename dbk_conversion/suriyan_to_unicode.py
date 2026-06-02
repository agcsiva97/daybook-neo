eng_to_tam = {
' ':' ',
' ':' ',
'q':'ளூ',
'w':'ற',
'e':'ந',
'r':'ச',
't':'வ',
'y':'ல',
'u':'ர',
'i':'ை',
'o':'டி',
'p':'ி',
'[':'ு',
']':'ூ',
'\\':'ஷ',
'a':'ய',
's':'ள',
'd':'ன',
'f':'க',
'g':'ப',
'h':'ா',
'j':'த',
'k':'ம',
'l':'ட',
';':'்',
'\'':'ங',
'z':'ண',
'x':'ஒ',
'c':'உ',
'v':'எ',
'b':'ெ',
'n':'ே',
'm':'அ',
',':'இ',
'.':'.',
'/':'/',
'1':'1',
'2':'2',
'3':'3',
'4':'4',
'5':'5',
'6':'6',
'7':'7',
'8':'8',
'9':'9',
'0':'0',
'-':'-',
'=':'=',
'Q':'ணு',
'W':'று',
'E':'நு',
'R':'சு',
'T':'கூ',
'Y':'லு',
'U':'ரு',
'I':'ஐ',
'O':'டீ',
'P':'ீ',
'{':'ு',
'}':'}',
'|':'ஞு',
'A':'ஹ',
'S':'ளு',
'D':'னு',
'F':'கு',
'G':'ழு',
'H':'ழ',
'J':'து',
'K':'மு',
'L':'டு',
':':':',
'"':'ஞ',
'Z':'ணு',
'X':'ஓ',
'C':'ஊ',
'V':'ஏ',
'B':'க்ஷ',
'N':'சூ',
'M':'ஆ',
'<':'ஈ',
'>':'ழூ',
'?':'?',
'!':'ஸ',
'@':'@',
'#':'ஜ',
'$':'ஶ்ரீ',
'%':'ரூ',
'^':'டூ',
'&':'ு',
'*':'*',
'(':'(',
')':')',
'_':'மூ',
'+':'+',
'-':'-'}

prepend_mapping = {
'J': 'j',
'Q': 'z',
'W': 'a',
'E': 'e',
'Y': 'y',
'|': '\"',
'D': 'd'
}

def convert_word(word):
    append_letter = ''
    converted_word = ''
    prepend_letter = ''
    skip_next = False
    if 'h;' in word:
        word = word.replace('h;', 'u;')
    if ';;' in word:
        word = word.replace(';;', ';')

    for i in range(len(word)):
        letter = word[i]
        if skip_next:
            skip_next = False
            continue
        if letter in ('b','n','i'):
            append_letter = letter
        elif letter in ('J','Q','W','E','Y','|','D'):
            if i + 1 < len(word):
                if word[i+1] == ']':
                    prepend_letter = prepend_mapping.get(letter)
                    converted_letter = convert_letter(prepend_letter)
                    converted_word += converted_letter + convert_letter(']')
                    skip_next = True
                else:
                    converted_letter = convert_letter(letter)
                    converted_word += converted_letter
            else:
                converted_letter = convert_letter(letter)
                converted_word += converted_letter
        else:
            converted_letter = convert_letter(letter)
            converted_word += converted_letter
            if append_letter:
                converted_word += convert_letter(append_letter)
            append_letter = ''
            
    return converted_word

def convert_letter(letter):
    if letter not in eng_to_tam:
        return ''
    return eng_to_tam.get(letter, letter)

# print(convert_word('gyngh;'))
# print(convert_word('Mjhafzf;Fgyngh; khk;g'))