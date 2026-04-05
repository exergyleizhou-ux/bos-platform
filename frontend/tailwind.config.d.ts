/**
 * BOS Pipeline v9.0 �� Tailwind CSS Configuration
 *
 * Custom theme tokens, fonts, shadows, and animation.
 */
declare const _default: {
    content: string[];
    darkMode: "class";
    theme: {
        extend: {
            colors: {
                surface: {
                    50: string;
                    100: string;
                    200: string;
                    300: string;
                    400: string;
                    500: string;
                    600: string;
                    700: string;
                    800: string;
                    900: string;
                    950: string;
                };
                brand: {
                    50: string;
                    100: string;
                    200: string;
                    300: string;
                    400: string;
                    500: string;
                    600: string;
                    700: string;
                    800: string;
                    900: string;
                };
            };
            fontFamily: {
                sans: [string, string, string, string, string, string];
                mono: [string, string, string, string, string, string];
            };
            boxShadow: {
                card: string;
                "card-hover": string;
            };
            animation: {
                "fade-in": string;
                "spin-slow": string;
            };
            keyframes: {
                "fade-in": {
                    "0%": {
                        opacity: string;
                        transform: string;
                    };
                    "100%": {
                        opacity: string;
                        transform: string;
                    };
                };
                "spin-slow": {
                    "0%": {
                        transform: string;
                    };
                    "100%": {
                        transform: string;
                    };
                };
            };
            spacing: {
                "18": string;
                "88": string;
                "112": string;
                "128": string;
            };
            fontSize: {
                "2xs": [string, {
                    lineHeight: string;
                }];
            };
            borderRadius: {
                "4xl": string;
            };
            zIndex: {
                "60": string;
                "70": string;
            };
        };
    };
    plugins: never[];
};
export default _default;
