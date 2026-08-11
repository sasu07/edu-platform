const MAX_EXPRESSION_LENGTH = 200;
const MAX_PARSE_DEPTH = 32;
const MAX_NORMALIZATION_PASSES = 16;

export function normalizeNumericExpression(value: string) {
  let expression = value.trim();
  if (!expression) return '';

  expression = expression.replace(/\$/g, '');
  expression = expression.replace(/^\s*[a-zA-Z]\s*=\s*/, '');

  if (expression.includes('=')) {
    const parts = expression.split('=').map((part) => part.trim()).filter(Boolean);
    expression = parts[parts.length - 1] || expression;
  }

  expression = expression.replace(/,/g, '.');
  expression = expression.replace(/\\left|\\right/g, '');
  expression = expression.replace(/\\text\{[^}]*\}/g, '');
  expression = expression.replace(/\\mathrm\{([^}]*)\}/g, '$1');
  expression = expression.replace(/\\cdot|\\times/g, '*');
  expression = expression.replace(/\\div/g, '/');
  expression = expression.replace(/\\pi/g, 'pi');

  const fractionPattern = /\\(?:d)?frac\s*\{([^{}]+)\}\{([^{}]+)\}/g;
  const squareRootPattern = /\\sqrt\s*\{([^{}]+)\}/g;
  for (let pass = 0; pass < MAX_NORMALIZATION_PASSES; pass += 1) {
    const previous = expression;
    expression = expression.replace(fractionPattern, '(($1)/($2))');
    expression = expression.replace(squareRootPattern, 'sqrt($1)');
    if (expression === previous) break;
  }

  return expression
    .replace(/\{/g, '(')
    .replace(/\}/g, ')')
    .replace(/\s+/g, '')
    .toLowerCase();
}

class NumericExpressionParser {
  private position = 0;
  private depth = 0;
  private readonly expression: string;

  constructor(expression: string) {
    this.expression = expression;
  }

  parse() {
    const result = this.parseExpression();
    if (this.position !== this.expression.length || !Number.isFinite(result)) {
      throw new Error('Invalid numeric expression');
    }
    return result;
  }

  private parseExpression(): number {
    let result = this.parseTerm();

    while (true) {
      if (this.consume('+')) result += this.parseTerm();
      else if (this.consume('-')) result -= this.parseTerm();
      else return result;
    }
  }

  private parseTerm(): number {
    let result = this.parseUnary();

    while (true) {
      if (this.consume('*')) {
        if (this.consume('*')) {
          this.position -= 2;
          return result;
        }
        result *= this.parseUnary();
      } else if (this.consume('/')) {
        result /= this.parseUnary();
      } else {
        return result;
      }
    }
  }

  private parseUnary(): number {
    if (this.consume('+')) return this.parseUnary();
    if (this.consume('-')) return -this.parseUnary();
    return this.parsePower();
  }

  private parsePower(): number {
    const base = this.parsePrimary();
    if (this.consume('**') || this.consume('^')) {
      return Math.pow(base, this.parseUnary());
    }
    return base;
  }

  private parsePrimary(): number {
    if (this.consume('(')) {
      this.depth += 1;
      if (this.depth > MAX_PARSE_DEPTH) throw new Error('Expression is too deeply nested');
      const result = this.parseExpression();
      if (!this.consume(')')) throw new Error('Missing closing parenthesis');
      this.depth -= 1;
      return result;
    }

    if (this.consume('sqrt')) {
      if (!this.consume('(')) throw new Error('sqrt requires parentheses');
      this.depth += 1;
      if (this.depth > MAX_PARSE_DEPTH) throw new Error('Expression is too deeply nested');
      const result = Math.sqrt(this.parseExpression());
      if (!this.consume(')')) throw new Error('Missing closing parenthesis');
      this.depth -= 1;
      return result;
    }

    if (this.consume('pi')) return Math.PI;

    const match = this.expression.slice(this.position).match(/^(?:\d+(?:\.\d*)?|\.\d+)/);
    if (!match) throw new Error('Expected a number');
    this.position += match[0].length;
    return Number(match[0]);
  }

  private consume(token: string) {
    if (!this.expression.startsWith(token, this.position)) return false;
    this.position += token.length;
    return true;
  }
}

export function evaluateNumericExpression(value: string): number | null {
  if (value.length > MAX_EXPRESSION_LENGTH) return null;
  const expression = normalizeNumericExpression(value);
  if (!expression || expression.length > MAX_EXPRESSION_LENGTH) return null;

  try {
    return new NumericExpressionParser(expression).parse();
  } catch {
    return null;
  }
}
