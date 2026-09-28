export type Country = {
    code: string,
    name: string
}

export type OperatorCountry = {
    isoName: string,
    name: string,
}

export type OperatorCurrency = {
    rate: number,
    currencyCode: number,
}

export type OperatorFx = {
    rate: number,
    currencyCode: string,
}

export type Operator = {
    operatorId: number,
    name: string,
    bundle: boolean,
    data: boolean,
    pin: boolean,
    comboProduct:  boolean,
    supportsLocalAmounts: boolean,
    supportsGeographicalRechargePlans: boolean,
    denominationType: string,
    senderCurrencyCode: string,
    senderCurrencySymbol: string,
    destinationCurrencyCode: string,
    destinationCurrencySymbol: string,
    commission: number,
    internationalDiscount: number,
    localDiscount: number,
    mostPopularAmount?: number | null,
    mostPopularLocalAmount?: number | null,
    minAmount?: number | null,
    maxAmount?: number | null,
    localMinAmount: number | null,
    country: OperatorCountry
    fx: OperatorFx
    logoUrls: string[] | null,
    fixedAmounts: number[] | null,
    fixedAmountsDescriptions: {[key: string]: string}[],
    localFixedAmounts: number[] | null,
    localFixedAmountsDescriptions: {[key: string]: string} | null,
    suggestedAmounts: number[] | null,
    suggestedAmountsMap: {[key: string]: number},
    fees: {[key: string]: number},
    geographicalRechargePlans: any[],
    promotions: any[] | null,
    status: string
}