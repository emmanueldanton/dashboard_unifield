from callbacks import auth, sync, tabs, filters, modals, interactions


def register_all_callbacks(app):
    auth.register(app)
    sync.register(app)
    tabs.register(app)
    filters.register(app)
    modals.register(app)
    interactions.register(app)
