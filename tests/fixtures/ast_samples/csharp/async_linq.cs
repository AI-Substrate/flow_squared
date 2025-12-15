using System.Linq;
using System.Threading.Tasks;
using System.Collections.Generic;

public class DataProcessor
{
    public async Task<List<Result>> ProcessAsync(IEnumerable<Input> inputs)
    {
        var filtered = inputs
            .Where(x => x.IsValid)
            .Select(x => new Result(x.Value));

        return await Task.FromResult(filtered.ToList());
    }
}
