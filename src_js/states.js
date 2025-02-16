
export const main = {
    form: {
        method: 'forward_greedy',
        cut_width: 0.3,
        min_initial_usage: false,
        native: false,
        panels: [],
        items: []
    },
    result: null,
    selected: {
        panel: null,
        item: null
    },
    calculating: false
};


export const panel = {
    name: 'Panel',
    quantity: 1,
    width: 100,
    height: 100
};


export const item = {
    name: 'Item',
    quantity: 1,
    width: 10,
    height: 10,
    can_rotate: true
};
