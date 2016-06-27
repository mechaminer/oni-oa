var React = require('react');

var GridPanelMixin = require('../../../js/components/GridPanelMixin.react');
var DetailsStore = require('../stores/DetailsStore');

var DetailsTablePanel = React.createClass({
  mixins: [GridPanelMixin],
  emptySetMessage: 'Please select one row from Suspicious DNS',
  getInitialState: function ()
  {
    return DetailsStore.getData();
  },
  componentDidMount: function ()
  {
    DetailsStore.addChangeDataListener(this._onChange);
  },
  componentWillUnmount: function ()
  {
    DetailsStore.removeChangeDataListener(this._onChange);
  },
  // Hidden cells
  _render_rip_cell: false,
  // Event handlers
  _onChange: function ()
  {
    this.setState(DetailsStore.getData());
    // After first load, set an empty message
    this.emptySetMessage = 'There is no information available';
  }
});

module.exports = DetailsTablePanel;
