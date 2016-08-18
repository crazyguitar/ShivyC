"""Classes for the nodes that form our abstract syntax tree (AST).

Each node corresponds to a rule in the C grammar and has a make_code function
that generates code in our three-address IL.

"""

import errors
import ctypes
import token_kinds
from il_gen import ILCode
from il_gen import TempILValue
from il_gen import LiteralILValue
from tokens import Token


class Node:
    """General class for representing a single node in the AST.

    Inherit all AST nodes from this class. Every AST node also has a make_code
    function that accepts a il_code (ILCode) to which the generated IL code
    should be saved.

    symbol (enum) - Non-terminal symbol the rule corresponding to a node
    produces. This value is checked by parent nodes to make sure the children
    produce symbols of the expected type.

    """

    # Enum for symbols produced by a node
    MAIN_FUNCTION = 1
    STATEMENT = 2
    DECLARATION = 3
    EXPRESSION = 4

    def __eq__(self, other):
        """Check whether all children of this node are equal."""
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def assert_symbol(self, node, symbol_name):
        """Check whether the provided node is of the given symbol.

        Useful for enforcing tree structure. Raises an exception if the node
        represents a rule that does not produce the expected symbol.

        """
        if node.symbol != symbol_name:
            raise ValueError("malformed tree: expected symbol '" + str(
                symbol_name) + "' but got '" + str(node.symbol) + "'")

    def assert_symbols(self, node, symbol_names):
        """Check whether the provided node is one of the given symbols.

        Useful for enforcing tree structure. Raises an exception if the node
        represents a rule that produces none of the symbols in symbol_names.

        """
        if node.symbol not in symbol_names:
            raise ValueError("malformed tree: unexpected symbol '" + str(
                node.symbol) + "'")

    def assert_kind(self, token, kind):
        """Check whether the provided token is of the given token kind.

        Useful for enforcing tree structure. Raises an exception if the token
        does not have the given kind.

        """
        if token.kind != kind:
            raise ValueError("malformed tree: expected token_kind '" + str(
                kind) + "' but got '" + str(token.kind) + "'")


class MainNode(Node):
    """General rule for the main function.

    This node will be removed once function definition is supported.

    block_items (List[statement, declaration]) - List of the statements and
    declarations in the main function.

    """

    symbol = Node.MAIN_FUNCTION

    def __init__(self, body):
        """Initialize node."""
        super().__init__()

        # Specifically, we expect 'body' to be a compound statement.
        self.assert_symbol(body, Node.STATEMENT)

        self.body = body

    def make_code(self, il_code, symbol_table):
        """Make IL code for the function body.

        At the end, this function adds code for an artificial return call
        for if the provided function body completes without returning.

        """
        self.body.make_code(il_code, symbol_table)

        return_node = ReturnNode(NumberNode(Token(token_kinds.number, "0")))
        return_node.make_code(il_code, symbol_table)


class CompoundNode(Node):
    """Rule for a compound node.

    A compound node is a statement that consists of several
    statements/declarations enclosed in braces.

    """

    symbol = Node.STATEMENT

    def __init__(self, block_items):
        """Initialize node."""
        super().__init__()

        for item in block_items:
            self.assert_symbols(item, [self.STATEMENT, self.DECLARATION])
        self.block_items = block_items

    def make_code(self, il_code, symbol_table):
        """Make IL code for every block item, in order."""
        for block_item in self.block_items:
            block_item.make_code(il_code, symbol_table)


class ReturnNode(Node):
    """Rule for the return statement.

    return_value (expression) - Value to return.

    """

    symbol = Node.STATEMENT

    def __init__(self, return_value):
        """Initialize node."""
        super().__init__()

        self.assert_symbol(return_value, self.EXPRESSION)

        self.return_value = return_value

    def make_code(self, il_code, symbol_table):
        """Make IL code for returning this value."""
        il_value = self.return_value.make_code(il_code, symbol_table)
        if il_value.ctype != ctypes.integer:
            # TODO: raise a type error
            raise NotImplementedError("type error")
        else:
            il_code.add_command(ILCode.RETURN, il_value)


class NumberNode(Node):
    """Expression that is just a single number.

    number (Token(Number)) - Number this expression represents.

    """

    symbol = Node.EXPRESSION

    def __init__(self, number):
        """Initialize node."""
        super().__init__()

        self.assert_kind(number, token_kinds.number)

        self.number = number

    def make_code(self, il_code, symbol_table):
        """Make code for a literal number.

        This function does not actually make any code in the IL, it just
        returns a LiteralILValue that can be used in IL code by the caller.

        """
        return LiteralILValue(ctypes.integer, str(self.number))


class IdentifierNode(Node):
    """Expression that is a single identifier.

    identifier (Token(Identifier)) - Identifier this expression represents.

    """

    symbol = Node.EXPRESSION

    def __init__(self, identifier):
        """Initialize node."""
        super().__init__()

        self.assert_kind(identifier, token_kinds.identifier)

        self.identifier = identifier

    def make_code(self, il_code, symbol_table):
        """Make code for an identifier.

        This function performs a lookup in the symbol table, and returns the
        corresponding ILValue.

        """
        return symbol_table.lookup(self.identifier.content)


class ExprStatementNode(Node):
    """Statement that contains just an expression."""

    symbol = Node.STATEMENT

    def __init__(self, expr):
        """Initialize node."""
        super().__init__()

        self.assert_symbol(expr, self.EXPRESSION)

        self.expr = expr

    def make_code(self, il_code, symbol_table):
        """Make code for the expression.

        An ILValue is returned, but we ignore it.

        """
        self.expr.make_code(il_code, symbol_table)


class ParenExprNode(Node):
    """Expression in parentheses."""

    symbol = Node.EXPRESSION

    def __init__(self, expr):
        """Initialize node."""
        super().__init__()

        self.assert_symbol(expr, self.EXPRESSION)

        self.expr = expr

    def make_code(self, il_code, symbol_table):
        """Make code for the expression in the parentheses."""
        return self.expr.make_code(il_code, symbol_table)


class IfStatementNode(Node):
    """If statement.

    conditional - Condition expression of the if statement.
    statement - Statement to be executed by the if statement. Note this is
    very often a compound-statement blocked out with curly braces.

    """

    symbol = Node.STATEMENT

    def __init__(self, conditional, statement):
        """Initialize node."""
        super().__init__()

        self.assert_symbol(conditional, Node.EXPRESSION)
        self.assert_symbol(statement, Node.STATEMENT)

        self.conditional = conditional
        self.statement = statement

    def make_code(self, il_code, symbol_table):
        """Make code for this node."""
        raise NotImplementedError


class BinaryOperatorNode(Node):
    """Expression that is a sum/difference/xor/etc of two expressions.

    left_expr (expression) - Expression on left side.
    operator (Token) - Token representing this operator.
    right_expr (expression) - Expression on right side.

    """

    symbol = Node.EXPRESSION

    def __init__(self, left_expr, operator, right_expr):
        """Initialize node."""
        super().__init__()

        self.assert_symbol(left_expr, self.EXPRESSION)
        self.assert_symbol(right_expr, self.EXPRESSION)

        self.left_expr = left_expr
        self.operator = operator
        self.right_expr = right_expr

    def make_code(self, il_code, symbol_table):
        """Make code for this node."""
        if self.operator == Token(token_kinds.plus):
            # TODO: Consider chosing intelligently which side to make code for
            # first.
            left = self.left_expr.make_code(il_code, symbol_table)
            right = self.right_expr.make_code(il_code, symbol_table)

            if left.ctype != ctypes.integer or right.ctype != ctypes.integer:
                raise NotImplementedError("type error")
            output = TempILValue(ctypes.integer)
            il_code.add_command(ILCode.ADD, left, right, output)
            return output
        elif self.operator == Token(token_kinds.star):
            # TODO: Consider chosing intelligently which side to make code for
            # first.
            left = self.left_expr.make_code(il_code, symbol_table)
            right = self.right_expr.make_code(il_code, symbol_table)

            if left.ctype != ctypes.integer or right.ctype != ctypes.integer:
                raise NotImplementedError("type error")
            output = TempILValue(ctypes.integer)
            il_code.add_command(ILCode.MULT, left, right, output)
            return output
        elif self.operator == Token(token_kinds.star):
            raise NotImplementedError("multiplication not supported")
        elif self.operator == Token(token_kinds.equals):
            if isinstance(self.left_expr, IdentifierNode):
                right = self.right_expr.make_code(il_code, symbol_table)
                left = symbol_table.lookup(self.left_expr.identifier.content)
                il_code.add_command(ILCode.SET, right, output=left)
                return left
            else:
                raise NotImplementedError("expected identifier on left side")
        else:
            raise errors.token_error("unsupported binary operator: '{}'",
                                     self.operator)


class DeclarationNode(Node):
    """Line of a general variable declaration(s).

    For example:  int a = 3, *b, c[] = {3, 2, 5};

    Currently, only supports declaration of a single integer variable with no
    initializer.

    variable_name (Token(identifier)) - The identifier representing the new
    variable name.

    """

    symbol = Node.DECLARATION

    def __init__(self, variable_name):
        """Initialize node."""
        super().__init__()

        self.assert_kind(variable_name, token_kinds.identifier)

        self.variable_name = variable_name

    def make_code(self, il_code, symbol_table):
        """Make code for this declaration.

        This function does not generate any IL code; it just adds the declared
        variable to the symbol table.

        """
        symbol_table.add(self.variable_name.content, ctypes.integer)