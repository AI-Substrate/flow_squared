/**
 * Authentication service with method call chains.
 * Line 3: auth.ts file
 */
import { validateString } from './utils';

/**
 * AuthService demonstrating various call patterns.
 * Line 9: AuthService class definition
 */
export class AuthService {
    private token: string | null = null;

    /**
     * Constructor calling private setup.
     * Line 15: constructor definition
     * Line 19: constructor → setup (same-file, private)
     */
    constructor() {
        this.setup();
    }

    /**
     * Private setup method.
     * Line 24: setup definition
     */
    private setup(): void {
        this.token = 'default';
    }

    /**
     * Login with method chain.
     * Line 31: login definition
     * Line 35: login → validate (same-file, public→private)
     */
    public login(user: string): boolean {
        return this.validate(user);
    }

    /**
     * Validate credentials with chain.
     * Line 40: validate definition
     * Line 44: validate → checkToken (same-file, chain)
     * Line 45: validate → validateString (cross-file)
     */
    private validate(user: string): boolean {
        const tokenOk = this.checkToken(user);
        const nameOk = validateString(user);
        return tokenOk && nameOk;
    }

    /**
     * Check token validity.
     * Line 51: checkToken definition
     */
    private checkToken(user: string): boolean {
        return this.token !== null && user.length > 0;
    }

    /**
     * Factory method calling constructor.
     * Line 58: create definition
     * Line 62: create → constructor (same-file, static→constructor)
     */
    public static create(): AuthService {
        return new AuthService();
    }
}
