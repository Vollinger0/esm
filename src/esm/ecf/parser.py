import copy
import re
import pyparsing as pp
from pathlib import Path
from typing import Any, List


class EcfProperty:
    """
        represents a single property / key-value pair
        values can be all kind of things though, due to what eleon allows.
    """
    def __init__(self, key: str, value: Any):
        self.key = key
        self.value = value
    
    def toDict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value
        }

class EcfExtendedProperty(EcfProperty):
    """
        A property that can have "extensions" to it, basically an list of properties following it. Worst way to re-invent complex objects.
            key: value, ext1: val1, ext2: val2, ext3: val3
    """
    def __init__(self, key: str, value: Any, extensions: List[EcfProperty]=None):
        super().__init__(key, value)
        self.extensions = extensions

    def fromDict(property: List, extensions: List) -> 'EcfExtendedProperty':
        if extensions and len(extensions) > 0:
            ecfExtensions = []
            for extension in extensions:
                ecfExtensions.append(EcfProperty(key=extension.get("key"), value=extension.get("value")))
            return EcfExtendedProperty(key=property[0], value=property[1], extensions=ecfExtensions)
        else:
            return EcfExtendedProperty(key=property[0], value=property[1])
        
    def toDict(self) -> dict:
        dict = super().toDict()
        if self.extensions and len(self.extensions) > 0:
            dict["extensions"] = [extension.toDict() for extension in self.extensions]
        return dict

class EcfChildBlock:
    """
        the child block object contained in another block, seems to be a special block, so we give it a special treatment.
    """
    def __init__(self, type: str, id: str, properties: List[EcfExtendedProperty]):
        self.type = type
        self.id = id
        self.properties = properties
    
    def fromDict(type: str, id: str, properties: List) -> 'EcfChildBlock':
        ecfProperties = []
        for property in properties:
            ecfProperties.append(EcfExtendedProperty.fromDict(property.get("property"), property.get("extensions")))
        return EcfChildBlock(type=type, id=id, properties=ecfProperties)
    
    def toDict(self) -> dict:
        dict = {
            "type": self.type,
            "id": self.id,
        }
        if self.properties and len(self.properties) > 0:
            dict["properties"] = [property.toDict() for property in self.properties]
        return dict

class EcfBlock:
    """
        a block object consisting of a block headerm and zero or more properties and child blocks
    """
    def __init__(self, type: str, qualifier: EcfExtendedProperty, properties: List[EcfExtendedProperty], children: List[EcfChildBlock]):
        self.type = type
        self.qualifier = qualifier
        self.properties = properties
        self.children = children

    def fromDict(block: dict) -> 'EcfBlock':
        # handle block header
        type = block.get("type")
        ecfBlockType = type
        
        header = block.get("header")[1]
        ecfBlockQualifier = EcfExtendedProperty.fromDict(header.get("property"), header.get("extensions"))
        
        contents = block.get("content")
        ecfProperties = []
        ecfChildBlocks = []
        for content in contents:
            if "type" in content.keys():
                # this is a child block
                type = content.get("type")
                id = content.get("id")
                properties = content.get("properties")
                ecfChildBlocks.append(EcfChildBlock.fromDict(type, id, properties))
            else:
                # this is a property
                ecfProperties.append(EcfExtendedProperty.fromDict(content.get("property"), content.get("extensions")))
        
        return EcfBlock(type=ecfBlockType, qualifier=ecfBlockQualifier, properties=ecfProperties, children=ecfChildBlocks)

    def toDict(self) -> dict:
        result = {
            "type": self.type,
            "qualifier": self.qualifier.toDict()
            }
        content = []
        if self.properties and len(self.properties) > 0:
            content.extend([property.toDict() for property in self.properties])
        if self.children and len(self.children) > 0:
            content.extend([child.toDict() for child in self.children])
        if content and len(content) > 0:
            result["content"] = content
        return result

class EcfFile:
    """
        represents a whole ecf file, which contains an optional version
        and a list of blocks
    """
    def __init__(self, version: str, blocks: List[EcfBlock]):
        self.version: str = version
        self.blocks: List[EcfBlock] = blocks

    def fromDict(fileData: dict) -> 'EcfFile':
        # set version
        ecfVersion = None
        if "version" in fileData.keys():
            ecfVersion = fileData.get("version")[0]

        # handle blocks
        blocks = fileData.get("blocks")
        ecfBlocks = []
        for block in blocks:
            ecfBlock = EcfBlock.fromDict(block)
            ecfBlocks.append(ecfBlock)
        return EcfFile(version=ecfVersion, blocks=ecfBlocks)

    def toDict(self) -> dict:
        dict = {}
        if self.version:
            dict["version"] = self.version
        if self.blocks and len(self.blocks) > 0:
            dict["blocks"] = [block.toDict() for block in self.blocks]
        return dict

class EcfParser:
    """
        main class for parsing ecf files from files or strings
    """
    transformNewLines: bool = False # set this to true if you want newlines in property values to be converted. should only be used for testing

    def _getGrammar():
        # Value can be quoted string, number, or unquoted string

        UNQUOTEDSTRING = pp.Word(pp.alphanums + "_-/@()[]. \\;|'!")
        UNQUOTEDSTRING.set_whitespace_chars(chars="\t\n\r")
        UNQUOTEDSTRING.setParseAction(lambda t: ''.join(t).strip())
        QUOTEDSTRING = pp.QuotedString('"') | pp.QuotedString("'")
        STRING = QUOTEDSTRING | UNQUOTEDSTRING

        NUMBER = pp.pyparsing_common.number

        BOOL_TRUE = pp.CaselessKeyword("true").setParseAction(lambda _: True)
        BOOL_FALSE = pp.CaselessKeyword("false").setParseAction(lambda _: False)
        BOOLEAN = BOOL_TRUE | BOOL_FALSE
        
        # # Handle special vector values like "1,0.6,0.1"
        #DQUOTE = pp.Suppress('"')
        #SQUOTE = pp.Suppress("'")
        #VECTOR = pp.Group(DQUOTE + pp.delimitedList(NUMBER) + DQUOTE) | pp.Group(SQUOTE + pp.delimitedList(NUMBER) + SQUOTE)
        # #VECTOR = (DQUOTE + pp.delimitedList(NUMBER) + DQUOTE) | (SQUOTE + pp.delimitedList(NUMBER) + SQUOTE)

        #propertyValue = BOOLEAN | VECTOR | NUMBER | STRING
        propertyValue = BOOLEAN | NUMBER | STRING

        propertyKey = (pp.Word(pp.alphas + "_", pp.alphanums + "_-.")).setParseAction(lambda t: t[0].strip())
        property = propertyKey("key") + pp.Suppress(":") + propertyValue("value")
    
        extendedProperty = (
            pp.Group(property("property") + pp.ZeroOrMore(pp.Suppress(",") + pp.Group(property))("extensions"))
            .setParseAction(EcfParser._parseWithMerge)
        )
        
        childblockHeader = pp.Opt(pp.Literal("+")).suppress() + pp.Word(pp.alphanums + "_")("type") + pp.Word(pp.alphanums+"_")("id")
        childblock = pp.Group(
            pp.Suppress("{") + childblockHeader("header") + 
            pp.ZeroOrMore(extendedProperty)("properties") + 
            pp.Suppress("}")
        ).setParseAction(EcfParser._parseWithMerge)
        
        blockHeader = pp.Opt(pp.Literal("+")).suppress() + pp.Word(pp.alphanums + "_")("type") + pp.Opt(pp.Literal(",")).suppress() + pp.Opt(extendedProperty)("props")
        block = pp.Group(
            pp.Suppress("{") + blockHeader("header") + 
            pp.ZeroOrMore(
                extendedProperty | childblock
            )("content") + 
            pp.Suppress("}")
        ).setParseAction(EcfParser._parseWithMerge)

        version = pp.Keyword("Version").suppress() + pp.Suppress(":") + pp.Word(pp.nums)

        file = (
            pp.Opt(version)("version") + 
            pp.OneOrMore(block)("blocks") +
            pp.ZeroOrMore(pp.Word(pp.printables)).suppress()
        )

        # this is only for debugging, slows down processing considerably!
        #file.set_debug()
        #file.set_debug(recurse=True)

        return file
    
    def readFromFile(filename: Path) -> EcfFile:
        #with open(filename, "r", encoding="utf-8-sig") as f:
        with open(filename, "r", encoding="utf-8-sig") as f:
            return EcfParser.readFromString(f.read())
        
    def readFromString(string: str) -> EcfFile:
        commentLessString = EcfParser._cleanString(string)
        parseResults = EcfParser._parseString(commentLessString)
        return EcfParser._readFromParseResults(parseResults)

    def _parseString(text) -> pp.ParseResults:
        return EcfParser._getGrammar().parseString(text, parse_all=True)
    
    def _readFromParseResults(parseResult: pp.ParseResults) -> EcfFile:
        result = parseResult.asDict()
        return EcfFile.fromDict(result)

    def _safeMerge(existing, new):
        """
        Safely merge dictionaries and lists without deep recursion
        """
        # If both are not dict-like, return the new value
        if not (isinstance(existing, (dict, pp.ParseResults)) and 
                isinstance(new, (dict, pp.ParseResults))):
            return new
        # Create a copy of the existing structure
        merged = copy.deepcopy(existing)
        # Iterate through new items
        for key, value in (new.items() if hasattr(new, 'items') else enumerate(new)):
            if key in merged:
                # If key exists, handle merging
                if isinstance(merged[key], list):
                    # For lists, extend without duplicates
                    if value not in merged[key]:
                        merged[key].append(value)
                elif isinstance(merged[key], (dict, pp.ParseResults)):
                    # For nested dicts/ParseResults, recursively merge
                    merged[key] = EcfParser._safeMerge(merged[key], value)
                else:
                    # For simple values, replace
                    merged[key] = value
            else:
                # If key doesn't exist, add it
                merged[key] = value
        return merged

    def _parseWithMerge(s, loc, tokens):
        """
        Parse action to merge nested results without deep recursion
        """
        if len(tokens) == 0:
            return tokens
        # Identify potential merge targets
        merge_keys = [k for k in tokens.keys() if isinstance(k, str) and k not in ['children']]
        if merge_keys:
            # Use the first identified key for merging
            key = merge_keys[0]
            # Create a new ParseResults with merged content
            merged_tokens = pp.ParseResults([])
            # Copy existing tokens
            for item in tokens:
                if item not in merged_tokens:
                    merged_tokens.append(item)
            # Merge dictionaries safely
            merged_tokens[key] = EcfParser._safeMerge(tokens.get(key, pp.ParseResults([])), tokens)
            return merged_tokens
        return tokens
    
    def _cleanString(text):
        """
            method to completely remove all comments from text
            easiest method, since using the pyparsing grammar seems to be impossible

            we also replace quoted \ns to their double escaped variants to avoid issues with pyparsing
        """
        # Remove multiline C-style comments while preserving quoted strings
        text = re.sub(r'(/\*.*?\*/)|("(?:\\.|[^"])*")', 
                    lambda m: m.group(2) if m.group(2) else '', 
                    text, 
                    flags=re.DOTALL)
        
        # Remove single-line comments while preserving quoted strings
        text = re.sub(r'(#.*$|//.*$)|("(?:\\.|[^"])*")', 
                    lambda m: m.group(2) if m.group(2) else '', 
                    text, 
                    flags=re.MULTILINE)
        
        # convert some special unicode signs into their ascii equivalent
        #text = unidecode.unidecode(text)
        text = re.sub("\u00E9", "e", text)
        text = re.sub("\u2019", "'", text)
        text = re.sub("\u00A0", " ", text)

        # replace \n with \\n in quoted strings
        if EcfParser.transformNewLines:
            text = re.sub(r'"[^"]*"', lambda match: match.group(0).replace('\n', '\\n'), text)
        return text    
