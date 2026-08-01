import { Amplify } from 'aws-amplify';
import {
    confirmSignUp,
    fetchAuthSession,
    getCurrentUser,
    resendSignUpCode,
    signIn,
    signOut,
    signUp
} from 'aws-amplify/auth';

const USER_POOL_ID = process.env.REACT_APP_COGNITO_USER_POOL_ID;
const CLIENT_ID = process.env.REACT_APP_COGNITO_CLIENT_ID;

/**
 * True when a user pool is configured.
 *
 * Without one the app runs exactly as it did before: the backends treat an unauthenticated
 * request as a local development user while AUTH_REQUIRED is off. That is what lets this ship
 * before the pool exists rather than as one flag-day switch.
 */
export const isAuthConfigured = Boolean(USER_POOL_ID && CLIENT_ID);

if (isAuthConfigured) {
    Amplify.configure({
        Auth: {
            Cognito: {
                userPoolId: USER_POOL_ID,
                userPoolClientId: CLIENT_ID,
                // SRP, so the password is never sent to Cognito and never passes through
                // this app's own code beyond the input element.
                loginWith: { username: false, email: true }
            }
        }
    });
}

/** The id token, which is what the backends verify. Null when not signed in. */
export const getIdToken = async () => {
    if (!isAuthConfigured) return null;
    try {
        const session = await fetchAuthSession();
        return session?.tokens?.idToken?.toString() || null;
    } catch (error) {
        // Not signed in, or the refresh token has expired. Either way there is no token.
        return null;
    }
};

export const getSignedInUser = async () => {
    if (!isAuthConfigured) return null;
    try {
        return await getCurrentUser();
    } catch (error) {
        return null;
    }
};

export const login = async (email, password) => {
    const result = await signIn({ username: email, password });
    // A user who signed up but never confirmed lands here rather than in the catch, so the
    // caller can send them to the confirmation step instead of showing "wrong password".
    if (result?.nextStep?.signInStep === 'CONFIRM_SIGN_UP') {
        return { needsConfirmation: true };
    }
    if (result?.nextStep && result.nextStep.signInStep !== 'DONE') {
        throw new Error(`This account needs to finish ${result.nextStep.signInStep} first.`);
    }
    return { needsConfirmation: false };
};

export const register = async (email, password) => {
    const result = await signUp({
        username: email,
        password,
        options: { userAttributes: { email } }
    });
    return { needsConfirmation: !result.isSignUpComplete };
};

export const confirm = (email, code) =>
    confirmSignUp({ username: email, confirmationCode: code });

export const resendCode = (email) => resendSignUpCode({ username: email });

export const logout = async () => {
    if (isAuthConfigured) {
        try {
            await signOut();
        } catch (error) {
            console.error('Sign out failed:', error);
        }
    }
    // These are not user-scoped, so leaving them behind would carry one person's pinned graph
    // layout and remembered project into the next person's session on a shared machine.
    try {
        Object.keys(window.localStorage)
            .filter((key) => key.startsWith('pami.'))
            .forEach((key) => window.localStorage.removeItem(key));
    } catch (error) {
        /* a blocked localStorage has nothing to clear */
    }
};

/** Human-readable text for the errors Cognito actually returns. */
export const describeAuthError = (error) => {
    const name = error?.name || '';
    switch (name) {
        case 'UserNotFoundException':
        case 'NotAuthorizedException':
            // Deliberately the same message for both: saying "no such user" tells anyone who
            // asks which email addresses have accounts here.
            return 'That email and password do not match an account.';
        case 'UserNotConfirmedException':
            return 'Please confirm your email address first.';
        case 'UsernameExistsException':
            return 'An account with that email already exists.';
        case 'InvalidPasswordException':
            return 'That password does not meet the requirements.';
        case 'CodeMismatchException':
            return 'That confirmation code is not right.';
        case 'ExpiredCodeException':
            return 'That code has expired. Ask for a new one.';
        case 'LimitExceededException':
        case 'TooManyRequestsException':
            return 'Too many attempts. Please wait a moment and try again.';
        default:
            return error?.message || 'Something went wrong. Please try again.';
    }
};
